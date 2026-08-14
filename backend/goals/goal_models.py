"""Agentic Goal Management Subsystem Data Models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any
import uuid

from backend.brain.workflow import TaskPlan


class GoalStatus(str, Enum):
    """Lifecycle status states for an Agentic Goal."""

    CREATED = "CREATED"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


@dataclass
class Goal:
    """Model representing a high-level user goal."""

    name: str
    goal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: GoalStatus = GoalStatus.CREATED
    sub_plans: list[TaskPlan] = field(default_factory=list)
    active_plan_index: int = 0
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    retry_count: int = 0
    max_retries: int = 3
    failure_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GoalProgress:
    """Real-time progress model for active goals."""

    goal_id: str
    status: GoalStatus
    percent_complete: float
    current_step_name: str
    elapsed_ms: float
