"""Dynamic Workflow Replacement & Mutation Engine."""

from __future__ import annotations

from threading import RLock

from backend.brain.workflow import TaskPlan, WorkflowEngine
from backend.core.events.bus import EventBus
from backend.utils.logger import get_logger
from backend.voice.streaming_events import WorkflowMutatedEvent
from backend.voice.streaming_models import StreamingPlannerAction

logger = get_logger(__name__)


class StreamingPlanner:
    """Dynamically replaces, appends, or cancels active TaskPlan sub-workflows."""

    def __init__(self, workflow_engine: WorkflowEngine, event_bus: EventBus | None = None) -> None:
        self._workflow_engine = workflow_engine
        self._event_bus = event_bus
        self._active_plan: TaskPlan | None = None
        self._lock = RLock()

    @property
    def active_plan(self) -> TaskPlan | None:
        return self._active_plan

    def replace_plan(self, new_plan: TaskPlan) -> bool:
        """Replace current active TaskPlan with a corrected plan in-flight."""
        with self._lock:
            old_name = self._active_plan.name if self._active_plan else "None"
            self._active_plan = new_plan
            logger.info("StreamingPlanner replaced plan '%s' -> '%s'", old_name, new_plan.name)

            if self._event_bus:
                self._event_bus.publish(
                    WorkflowMutatedEvent(
                        action=StreamingPlannerAction.REPLACE_PLAN.value,
                        plan_name=new_plan.name,
                    )
                )
            return True

    def cancel_active(self) -> bool:
        """Instantly cancel active TaskPlan execution."""
        with self._lock:
            if self._active_plan:
                plan_name = self._active_plan.name
                self._active_plan = None
                logger.info("StreamingPlanner cancelled active plan '%s'", plan_name)

                if self._event_bus:
                    self._event_bus.publish(
                        WorkflowMutatedEvent(
                            action=StreamingPlannerAction.CANCEL_STEPS.value,
                            plan_name=plan_name,
                        )
                    )
                return True
            return False
