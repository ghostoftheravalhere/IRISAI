"""Context manager service coordinating short-term operational context and persistence."""

from __future__ import annotations

from typing import Any

from backend.brain.context_store import ContextSnapshot, ContextStore, InMemoryContextStore
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ContextManager:
    """Manages short-term operational context using an abstract ContextStore persistence engine."""

    def __init__(self, store: ContextStore | None = None) -> None:
        self._store = store or InMemoryContextStore()

    @property
    def store(self) -> ContextStore:
        """Return the underlying ContextStore instance."""
        return self._store

    def record_utterance(
        self,
        transcript: str,
        intent: str | None = None,
        normalized_transcript: str = "",
        active_app: str | None = None,
        status: str = "Completed",
        session_id: str = "default",
        metadata: dict[str, Any] | None = None,
    ) -> ContextSnapshot:
        """Record an operational perception/execution utterance snapshot."""
        snapshot = ContextSnapshot(
            session_id=session_id,
            intent=intent,
            raw_transcript=transcript,
            normalized_transcript=normalized_transcript or transcript,
            active_application=active_app,
            execution_status=status,
            metadata=metadata or {},
        )
        self._store.save_snapshot(snapshot)
        return snapshot

    def add_utterance(self, transcript: str) -> ContextSnapshot:
        """Alias for record_utterance for backward compatibility."""
        return self.record_utterance(transcript)

    def get_current_context(self, session_id: str = "default") -> dict[str, Any]:
        """Return structured current operational context for a session."""
        latest = self._store.get_latest(session_id)
        return {
            "hasContext": latest is not None,
            "sessionId": session_id,
            "latest": latest,
        }

    def get_recent_history(self, session_id: str = "default", limit: int = 10) -> list[ContextSnapshot]:
        """Retrieve recent non-expired context snapshots for a session."""
        return self._store.get_history(session_id=session_id, limit=limit)

    def get_context(self) -> ContextSnapshot:
        """Return latest snapshot or empty snapshot for backward compatibility."""
        latest = self._store.get_latest("default")
        return latest or ContextSnapshot()

    def pass_through(self, context: ContextSnapshot) -> ContextSnapshot:
        """Return an existing context unchanged for backward compatibility."""
        return context
