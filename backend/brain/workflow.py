"""Task & Workflow Engine for multi-step task execution, retries, rollbacks, and cancellation."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
import time
from typing import Any, Sequence
import uuid

from backend.automation.dispatcher import AutomationDispatcher
from backend.brain.workflow_events import (
    WorkflowCompletedEvent,
    WorkflowFailedEvent,
    WorkflowStartedEvent,
    WorkflowStepCompletedEvent,
)
from backend.core.events.bus import EventBus
from backend.utils.logger import get_logger
from backend.voice.command_parser import VoiceIntent, VoiceIntentType

logger = get_logger(__name__)


from backend.perception.ui_automation_models import InteractionMode


@dataclass
class WorkflowStep:
    """Represents a single executable action step within a TaskPlan."""

    intent: str
    target: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    rollback_intent: str | None = None
    status: str = "PENDING"
    interaction_mode: InteractionMode = InteractionMode.HYBRID
    step_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class TaskPlan:
    """Represents a structured sequence of WorkflowSteps to execute."""

    name: str = "TaskPlan"
    steps: list[WorkflowStep] = field(default_factory=list)
    session_id: str = "default"
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class CancellationToken:
    """Thread-safe token used to request execution cancellation of a running workflow."""

    def __init__(self) -> None:
        self._cancelled = False
        self._lock = RLock()

    def cancel(self) -> None:
        """Signal cancellation."""
        with self._lock:
            self._cancelled = True

    def is_cancelled(self) -> bool:
        """Return True if cancellation has been requested."""
        with self._lock:
            return self._cancelled


@dataclass
class ProgressTracker:
    """Tracks current step progress of a TaskPlan."""

    total_steps: int = 0
    completed_steps: int = 0
    current_step_index: int = 0

    def advance(self) -> None:
        """Advance progress metrics."""
        self.completed_steps += 1
        self.current_step_index += 1


@dataclass
class RetryPolicy:
    """Configurable policy for handling transient step execution failures."""

    max_retries: int = 2
    delay_seconds: float = 0.05


from backend.agent.verification_engine import VerificationEngine


class WorkflowEngine:
    """Engine responsible for coordinating multi-step TaskPlan execution."""

    def __init__(
        self,
        automation_dispatcher: AutomationDispatcher,
        event_bus: EventBus | None = None,
        retry_policy: RetryPolicy | None = None,
        enabled: bool = True,
        verification_engine: VerificationEngine | None = None,
    ) -> None:
        self._automation_dispatcher = automation_dispatcher
        self._event_bus = event_bus
        self._retry_policy = retry_policy or RetryPolicy()
        self._enabled = enabled
        self._verifier = verification_engine or VerificationEngine(event_bus=event_bus)
        self._lock = RLock()

    @property
    def enabled(self) -> bool:
        """Return whether workflow engine is active."""
        return self._enabled

    def replace_step(self, plan: TaskPlan, step_index: int, new_step: WorkflowStep) -> bool:
        """Replace a failed step in TaskPlan in-place."""
        with self._lock:
            if 0 <= step_index < len(plan.steps):
                logger.info("WorkflowEngine replace_step at index %d: '%s' -> '%s'", step_index, plan.steps[step_index].intent, new_step.intent)
                plan.steps[step_index] = new_step
                return True
            return False

    def insert_step(self, plan: TaskPlan, step_index: int, new_step: WorkflowStep) -> bool:
        """Insert a step into TaskPlan at step_index."""
        with self._lock:
            idx = max(0, min(step_index, len(plan.steps)))
            logger.info("WorkflowEngine insert_step at index %d: '%s'", idx, new_step.intent)
            plan.steps.insert(idx, new_step)
            return True

    def skip_step(self, plan: TaskPlan, step_index: int) -> bool:
        """Skip a non-critical step in TaskPlan."""
        with self._lock:
            if 0 <= step_index < len(plan.steps):
                logger.info("WorkflowEngine skip_step at index %d: '%s'", step_index, plan.steps[step_index].intent)
                plan.steps[step_index].status = "SKIPPED"
                plan.steps.pop(step_index)
                return True
            return False

    def merge_steps(self, plan: TaskPlan, start_index: int, end_index: int, replacement_steps: list[WorkflowStep]) -> bool:
        """Consolidate a slice of workflow steps with replacement_steps."""
        with self._lock:
            if 0 <= start_index <= end_index <= len(plan.steps):
                logger.info("WorkflowEngine merge_steps indices [%d:%d] with %d replacement step(s)", start_index, end_index, len(replacement_steps))
                plan.steps[start_index:end_index] = replacement_steps
                return True
            return False

    def _resolve_intent(self, intent_str: str, target: str | None = None, params: dict[str, Any] | None = None) -> VoiceIntent:
        """Resolve string intent name to VoiceIntent enum object."""
        intent_enum = VoiceIntentType.NO_INTENT
        i_upper = intent_str.upper()
        if i_upper == "SEARCH_BROWSER":
            intent_enum = VoiceIntentType.BROWSER_SEARCH
        else:
            for member in VoiceIntentType:
                if member.value == intent_str or member.name == intent_str:
                    intent_enum = member
                    break
        query = params.get("text") or params.get("query") if params else None
        return VoiceIntent(intent=intent_enum, text=intent_str, target=target, query=query, params=params or {})

    def _rollback_executed(self, completed_steps: list[WorkflowStep]) -> None:
        """Execute inverse rollback steps in reverse order."""
        logger.warning("Initiating workflow rollback for %d steps", len(completed_steps))
        for step in reversed(completed_steps):
            if step.rollback_intent:
                logger.info("Executing rollback step '%s' for step %s", step.rollback_intent, step.step_id)
                rb_intent = self._resolve_intent(step.rollback_intent, step.target, step.params)
                self._automation_dispatcher.dispatch(rb_intent)

    def execute_plan(self, plan: TaskPlan, cancel_token: CancellationToken | None = None) -> bool:
        """Execute a TaskPlan sequentially with retry, rollback, and cancellation support."""
        if not self._enabled:
            logger.info("WorkflowEngine disabled; falling back.")
            return False

        t0 = time.time()
        total_steps = len(plan.steps)
        if self._event_bus:
            self._event_bus.publish(
                WorkflowStartedEvent(
                    plan_id=plan.plan_id,
                    plan_name=plan.name,
                    total_steps=total_steps,
                )
            )

        executed_steps: list[WorkflowStep] = []
        tracker = ProgressTracker(total_steps=total_steps)

        with self._lock:
            for idx, step in enumerate(plan.steps):
                if cancel_token and cancel_token.is_cancelled():
                    logger.warning("Workflow '%s' cancelled at step %d", plan.name, idx)
                    self._rollback_executed(executed_steps)
                    if self._event_bus:
                        self._event_bus.publish(
                            WorkflowFailedEvent(
                                plan_id=plan.plan_id,
                                failed_step_id=step.step_id,
                                reason="Cancelled by CancellationToken",
                                rolled_back=True,
                            )
                        )
                    return False

                voice_intent = self._resolve_intent(step.intent, step.target, step.params)

                # Step execution & self-verification loop with exponential backoff
                step_success = False
                attempts = 0
                while attempts <= self._retry_policy.max_retries and not step_success:
                    attempts += 1
                    result = self._automation_dispatcher.dispatch(voice_intent)
                    if result.success:
                        # Perform self-verification
                        if hasattr(self, "_verifier") and self._verifier:
                            v_res = self._verifier.verify_action(
                                action_name=step.intent,
                                target=step.target or "",
                            )
                            step_success = v_res.success
                        else:
                            step_success = True

                    if not step_success and attempts <= self._retry_policy.max_retries:
                        backoff = self._retry_policy.delay_seconds * (2 ** (attempts - 1))
                        time.sleep(backoff)

                if step_success:
                    step.status = "COMPLETED"
                    executed_steps.append(step)
                    tracker.advance()
                    if self._event_bus:
                        self._event_bus.publish(
                            WorkflowStepCompletedEvent(
                                plan_id=plan.plan_id,
                                step_id=step.step_id,
                                step_index=idx,
                                intent=step.intent,
                            )
                        )
                else:
                    step.status = "FAILED"
                    logger.error("Workflow step '%s' failed after %d attempts", step.intent, attempts)
                    self._rollback_executed(executed_steps)
                    if self._event_bus:
                        self._event_bus.publish(
                            WorkflowFailedEvent(
                                plan_id=plan.plan_id,
                                failed_step_id=step.step_id,
                                reason=f"Step '{step.intent}' failed execution after retries",
                                rolled_back=True,
                            )
                        )
                    return False

            duration_ms = (time.time() - t0) * 1000.0
            if self._event_bus:
                self._event_bus.publish(
                    WorkflowCompletedEvent(
                        plan_id=plan.plan_id,
                        total_steps=total_steps,
                        execution_time_ms=duration_ms,
                    )
                )
            return True
