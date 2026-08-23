"""In-memory session memory stub for future runtime history."""

from __future__ import annotations

from collections import deque


class SessionMemory:
    """Bounded in-memory event store with no persistence or file IO."""

    def __init__(self, max_events: int = 100) -> None:
        if max_events < 1:
            raise ValueError("max_events must be at least 1.")
        self._events: deque[object] = deque(maxlen=max_events)

    def append(self, event: object) -> None:
        """Append one in-session event."""
        self._events.append(event)

    def get_events(self) -> tuple[object, ...]:
        """Return a snapshot of stored events."""
        return tuple(self._events)

    def clear(self) -> None:
        """Clear stored session events."""
        self._events.clear()

    def __len__(self) -> int:
        return len(self._events)
