"""Context manager stub for future runtime context assembly."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContextSnapshot:
    """Placeholder runtime context snapshot."""

    data: dict[str, Any] = field(default_factory=dict)


class ContextManager:
    """Return empty/pass-through context until future sprints add sources."""

    def get_context(self) -> ContextSnapshot:
        """Return an empty context snapshot."""
        return ContextSnapshot()

    def pass_through(self, context: ContextSnapshot) -> ContextSnapshot:
        """Return an existing context unchanged."""
        return context
