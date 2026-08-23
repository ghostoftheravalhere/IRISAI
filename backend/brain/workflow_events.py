"""Domain events emitted during workflow execution."""

from __future__ import annotations

from dataclasses import dataclass

from backend.core.events.bus import DomainEvent


@dataclass
class WorkflowStartedEvent(DomainEvent):
    """Event emitted when a multi-step TaskPlan execution begins."""

    plan_id: str = ""
    plan_name: str = ""
    total_steps: int = 0


@dataclass
class WorkflowStepCompletedEvent(DomainEvent):
    """Event emitted when an individual workflow step completes successfully."""

    plan_id: str = ""
    step_id: str = ""
    step_index: int = 0
    intent: str = ""


@dataclass
class WorkflowFailedEvent(DomainEvent):
    """Event emitted when a workflow step fails unrecoverably."""

    plan_id: str = ""
    failed_step_id: str = ""
    reason: str = ""
    rolled_back: bool = False


@dataclass
class WorkflowCompletedEvent(DomainEvent):
    """Event emitted when a TaskPlan completes all steps."""

    plan_id: str = ""
    total_steps: int = 0
    execution_time_ms: float = 0.0
