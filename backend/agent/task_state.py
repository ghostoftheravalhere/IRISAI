"""Task State dataclasses and operational memory encapsulation for Agent Core."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import uuid
from typing import Any


class TaskStatus(str, Enum):
    """Execution status of an active agent task."""

    IDLE = "IDLE"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    WAITING_CLARIFICATION = "WAITING_CLARIFICATION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class PlanStep:
    """Individual executable step within an Agent Plan."""

    step_id: int
    tool_name: str
    description: str
    params: dict[str, Any] = field(default_factory=dict)
    status: str = "PENDING"  # PENDING, IN_PROGRESS, COMPLETED, FAILED
    result: Any | None = None


@dataclass
class Plan:
    """Multi-step execution plan for achieving a user goal."""

    goal: str
    steps: list[PlanStep] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        """Return True if all plan steps are completed."""
        return len(self.steps) > 0 and all(step.status == "COMPLETED" for step in self.steps)


@dataclass
class TaskState:
    """Encapsulates active transient task context, step history, and operational context."""

    user_goal: str
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.IDLE
    current_plan: Plan | None = None
    current_step_index: int = 0
    history: list[tuple[PlanStep, Any]] = field(default_factory=list)
    active_application: str | None = None
    active_window: str | None = None
    last_resolved_target: str | None = None
    pending_confirmation: dict[str, Any] | None = None
    error_message: str | None = None

    def advance_step(self, step: PlanStep, result: Any) -> None:
        """Record step completion and advance to the next step index."""
        step.status = "COMPLETED" if getattr(result, "success", True) else "FAILED"
        step.result = result
        self.history.append((step, result))
        self.current_step_index += 1

    def fail_task(self, reason: str) -> None:
        """Mark task as failed with reason."""
        self.status = TaskStatus.FAILED
        self.error_message = reason
