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
    """Encapsulates active transient task context, candidate ambiguity memory, step history, and operational context."""

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
    candidates: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    last_tool_result: Any | None = None
    user_correction: dict[str, Any] | None = None
    error_message: str | None = None

    def advance_step(self, step: PlanStep, result: Any) -> None:
        """Record step completion and advance to the next step index."""
        step.status = "COMPLETED" if getattr(result, "success", True) else "FAILED"
        step.result = result
        self.last_tool_result = result
        self.history.append((step, result))
        self.current_step_index += 1

        # Extract candidates or sources if present in tool result data
        if hasattr(result, "data") and isinstance(result.data, dict):
            if "candidates" in result.data and result.data["candidates"]:
                self.candidates = result.data["candidates"]
            if "sources" in result.data and result.data["sources"]:
                self.sources = result.data["sources"]

    def fail_task(self, reason: str) -> None:
        """Mark task as failed with reason."""
        self.status = TaskStatus.FAILED
        self.error_message = reason

    def resolve_candidate(self, user_selection: str) -> dict[str, Any] | None:
        """Resolve a candidate entry from user selection phrase (e.g. 'the second one' -> candidate index 2)."""
        if not self.candidates:
            return None

        text = user_selection.lower().strip()
        ordinal_map = {
            "first": 1, "1st": 1, "one": 1, "1": 1,
            "second": 2, "2nd": 2, "two": 2, "2": 2,
            "third": 3, "3rd": 3, "three": 3, "3": 3,
            "fourth": 4, "4th": 4, "four": 4, "4": 4,
            "fifth": 5, "5th": 5, "five": 5, "5": 5,
        }

        for term, index in ordinal_map.items():
            if term in text:
                for c in self.candidates:
                    if c.get("index") == index:
                        self.last_resolved_target = c.get("path") or c.get("name")
                        return c

        # Fallback to returning candidate 1
        self.last_resolved_target = self.candidates[0].get("path") or self.candidates[0].get("name")
        return self.candidates[0]
