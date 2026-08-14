"""Goal Lifecycle State Machine Manager."""

from __future__ import annotations

from backend.goals.goal_models import Goal, GoalStatus
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Valid state transitions
_VALID_TRANSITIONS: dict[GoalStatus, set[GoalStatus]] = {
    GoalStatus.CREATED: {GoalStatus.PLANNING, GoalStatus.CANCELLED},
    GoalStatus.PLANNING: {GoalStatus.EXECUTING, GoalStatus.FAILED, GoalStatus.CANCELLED},
    GoalStatus.EXECUTING: {GoalStatus.WAITING, GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.CANCELLED},
    GoalStatus.WAITING: {GoalStatus.EXECUTING, GoalStatus.CANCELLED, GoalStatus.FAILED},
    GoalStatus.COMPLETED: set(),
    GoalStatus.CANCELLED: set(),
    GoalStatus.FAILED: {GoalStatus.PLANNING, GoalStatus.CREATED},  # Retries allowed
}


class GoalStateMachine:
    """Enforces valid lifecycle transitions for Agentic Goals."""

    @staticmethod
    def transition(goal: Goal, target_status: GoalStatus) -> bool:
        """Attempt to transition goal state; returns True if valid."""
        allowed = _VALID_TRANSITIONS.get(goal.status, set())
        if target_status not in allowed:
            logger.warning(
                "Illegal Goal state transition attempt: %s -> %s (goal_id=%s)",
                goal.status.value,
                target_status.value,
                goal.goal_id,
            )
            return False

        logger.info(
            "Goal %s transitioned state: %s -> %s",
            goal.goal_id,
            goal.status.value,
            target_status.value,
        )
        goal.status = target_status
        return True
