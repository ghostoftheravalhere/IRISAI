"""Domain events emitted by the Multimodal Fusion Engine."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.core.events.bus import DomainEvent


@dataclass
class FusionAttemptedEvent(DomainEvent):
    """Event emitted when Multimodal Fusion Engine evaluates perception events."""

    event_count: int = 0
    sources: list[str] = field(default_factory=list)
    window_ms: float = 500.0


@dataclass
class FusionCompletedEvent(DomainEvent):
    """Event emitted when a fused multimodal intent command is generated."""

    unified_intent: str = ""
    combined_confidence: float = 0.0
    selected_rule: str = ""
    target: str | None = None
