"""Streaming Intelligence Domain Events."""

from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass(frozen=True)
class PartialTranscriptEvent:
    """Event emitted when a partial transcript frame is recognized."""

    text: str
    is_final: bool
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class PartialIntentPredictedEvent:
    """Event emitted when a tentative intent is predicted from partial transcript."""

    intent_name: str
    target: str | None
    is_stable: bool
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class WorkflowMutatedEvent:
    """Event emitted when a TaskPlan is dynamically replaced, appended, or cancelled."""

    action: str
    plan_name: str
    timestamp: float = field(default_factory=time.time)
