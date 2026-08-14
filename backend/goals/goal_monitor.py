"""Goal Execution Monitor & Metrics Service."""

from __future__ import annotations

import time

from backend.goals.goal_models import Goal, GoalProgress
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GoalMonitor:
    """Monitors real-time progress, step metrics, and duration of active goals."""

    def get_progress(self, goal: Goal) -> GoalProgress:
        """Calculate real-time GoalProgress metrics."""
        total = len(goal.sub_plans)
        if total == 0:
            percent = 0.0
            step_name = "None"
        else:
            percent = min(100.0, (goal.active_plan_index / total) * 100.0)
            step_name = goal.sub_plans[goal.active_plan_index].name if goal.active_plan_index < total else "Completed"

        elapsed = (time.time() - goal.created_at) * 1000.0

        return GoalProgress(
            goal_id=goal.goal_id,
            status=goal.status,
            percent_complete=percent,
            current_step_name=step_name,
            elapsed_ms=elapsed,
        )
