"""Goal Subsystem Domain Events."""

from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass(frozen=True)
class GoalCreatedEvent:
    """Event emitted when a new goal is created."""

    goal_id: str
    name: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class GoalStatusChangedEvent:
    """Event emitted when a goal transitions lifecycle status."""

    goal_id: str
    old_status: str
    new_status: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class GoalProgressUpdatedEvent:
    """Event emitted when goal execution progress updates."""

    goal_id: str
    percent_complete: float
    current_step_name: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class GoalCompletedEvent:
    """Event emitted when a goal successfully completes."""

    goal_id: str
    duration_ms: float
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class GoalFailedEvent:
    """Event emitted when a goal fails after retries."""

    goal_id: str
    reason: str
    timestamp: float = field(default_factory=time.time)
