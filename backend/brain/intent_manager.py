"""Intent manager stub for future multi-modal intent coordination."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.core.contracts.intent import Confidence, Intent, IntentSource


@dataclass(frozen=True)
class IntentRecord:
    """Concrete placeholder intent that satisfies the Sprint 1 contract."""

    name: str
    source: IntentSource = IntentSource.UNKNOWN
    confidence: Confidence = field(default_factory=lambda: Confidence(1.0))
    payload: dict[str, Any] = field(default_factory=dict)


class IntentManager:
    """Pass-through intent facade for future Brain orchestration."""

    def create_intent(
        self,
        name: str,
        source: IntentSource = IntentSource.UNKNOWN,
        confidence: Confidence | None = None,
        payload: dict[str, Any] | None = None,
    ) -> IntentRecord:
        """Create a contract-compatible intent without interpretation logic."""
        return IntentRecord(
            name=name,
            source=source,
            confidence=confidence or Confidence(1.0),
            payload=dict(payload or {}),
        )

    def pass_through(self, intent: Intent) -> Intent:
        """Return an existing intent unchanged."""
        return intent
