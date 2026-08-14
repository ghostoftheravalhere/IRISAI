"""Sequential Goal Sub-Plan Executor Service."""

from __future__ import annotations

import time
from typing import Any

from backend.brain.workflow import WorkflowEngine
from backend.core.events.bus import EventBus
from backend.goals.goal_events import (
    GoalCompletedEvent,
    GoalFailedEvent,
    GoalProgressUpdatedEvent,
)
from backend.goals.goal_models import Goal, GoalStatus
from backend.goals.goal_state_machine import GoalStateMachine
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GoalExecutor:
    """Sequentially executes sub-plans of an Agentic Goal via WorkflowEngine."""

    def __init__(
        self,
        workflow_engine: WorkflowEngine,
        event_bus: EventBus | None = None,
    ) -> None:
        self._workflow_engine = workflow_engine
        self._event_bus = event_bus

    def execute_goal(self, goal: Goal) -> bool:
        """Execute all sub-plans for a goal sequentially."""
        if not goal.sub_plans:
            GoalStateMachine.transition(goal, GoalStatus.FAILED)
            goal.failure_reason = "No executable sub-plans found."
            return False

        GoalStateMachine.transition(goal, GoalStatus.EXECUTING)
        t0 = time.time()
        total_plans = len(goal.sub_plans)

        for idx, sub_plan in enumerate(goal.sub_plans):
            goal.active_plan_index = idx
            percent = ((idx) / total_plans) * 100.0

            if self._event_bus:
                self._event_bus.publish(
                    GoalProgressUpdatedEvent(
                        goal_id=goal.goal_id,
                        percent_complete=percent,
                        current_step_name=sub_plan.name,
                    )
                )

            if goal.status == GoalStatus.CANCELLED:
                logger.info("Goal %s execution cancelled by token.", goal.goal_id)
                return False

            success = self._workflow_engine.execute_plan(sub_plan)
            if not success:
                logger.warning("Sub-plan '%s' failed in goal %s", sub_plan.name, goal.goal_id)
                GoalStateMachine.transition(goal, GoalStatus.FAILED)
                goal.failure_reason = f"Sub-plan '{sub_plan.name}' failed."
                if self._event_bus:
                    self._event_bus.publish(
                        GoalFailedEvent(goal_id=goal.goal_id, reason=goal.failure_reason)
                    )
                return False

        duration_ms = (time.time() - t0) * 1000.0
        GoalStateMachine.transition(goal, GoalStatus.COMPLETED)
        goal.completed_at = time.time()

        if self._event_bus:
            self._event_bus.publish(
                GoalProgressUpdatedEvent(
                    goal_id=goal.goal_id,
                    percent_complete=100.0,
                    current_step_name="Completed",
                )
            )
            self._event_bus.publish(
                GoalCompletedEvent(goal_id=goal.goal_id, duration_ms=duration_ms)
            )

        logger.info("Goal %s completed successfully in %.2f ms", goal.goal_id, duration_ms)
        return True
