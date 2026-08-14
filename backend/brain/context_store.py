"""Context storage abstractions and in-memory operational state store."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from threading import RLock
import time
from typing import Any, Protocol
import uuid

from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ContextSnapshot:
    """Operational state snapshot representing a single perception/execution frame."""

    session_id: str = "default"
    timestamp: float = field(default_factory=time.time)
    intent: str | None = None
    raw_transcript: str = ""
    normalized_transcript: str = ""
    active_application: str | None = None
    execution_status: str = "Completed"
    metadata: dict[str, Any] = field(default_factory=dict)
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def data(self) -> dict[str, Any]:
        """Backward compatibility alias for metadata."""
        return self.metadata


class ContextStore(Protocol):
    """Protocol defining abstract persistence interface for short-term context."""

    def save_snapshot(self, snapshot: ContextSnapshot) -> None:
        """Save a context snapshot frame."""
        ...

    def get_latest(self, session_id: str = "default") -> ContextSnapshot | None:
        """Retrieve the most recent valid snapshot for a session."""
        ...

    def get_history(self, session_id: str = "default", limit: int = 10) -> list[ContextSnapshot]:
        """Retrieve non-expired snapshot history for a session."""
        ...

    def clear(self, session_id: str | None = None) -> None:
        """Clear context snapshots for a session or all sessions."""
        ...


class InMemoryContextStore:
    """Thread-safe in-memory store enforcing rolling max capacity and TTL expiration."""

    def __init__(self, max_snapshots: int = 50, ttl_seconds: float = 300.0) -> None:
        self._max_snapshots = max_snapshots
        self._ttl_seconds = ttl_seconds
        self._store: dict[str, deque[ContextSnapshot]] = {}
        self._lock = RLock()

    def save_snapshot(self, snapshot: ContextSnapshot) -> None:
        """Save a snapshot into session deque, enforcing max snapshot limit."""
        with self._lock:
            sid = snapshot.session_id
            if sid not in self._store:
                self._store[sid] = deque(maxlen=self._max_snapshots)
            self._store[sid].append(snapshot)
            logger.debug("Saved context snapshot %s for session '%s'", snapshot.snapshot_id, sid)

    def _filter_expired(self, snapshots: list[ContextSnapshot]) -> list[ContextSnapshot]:
        """Filter out snapshots exceeding the TTL expiration threshold."""
        now = time.time()
        return [s for s in snapshots if (now - s.timestamp) <= self._ttl_seconds]

    def get_latest(self, session_id: str = "default") -> ContextSnapshot | None:
        """Retrieve the latest non-expired snapshot for a session."""
        with self._lock:
            session_deq = self._store.get(session_id)
            if not session_deq:
                return None
            valid = self._filter_expired(list(session_deq))
            return valid[-1] if valid else None

    def get_history(self, session_id: str = "default", limit: int = 10) -> list[ContextSnapshot]:
        """Retrieve up to `limit` recent non-expired snapshots for a session."""
        with self._lock:
            session_deq = self._store.get(session_id)
            if not session_deq:
                return []
            valid = self._filter_expired(list(session_deq))
            return valid[-limit:]

    def clear(self, session_id: str | None = None) -> None:
        """Clear context snapshots for a target session or all sessions."""
        with self._lock:
            if session_id is not None:
                if session_id in self._store:
                    self._store[session_id].clear()
            else:
                self._store.clear()
