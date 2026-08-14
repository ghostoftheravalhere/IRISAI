"""Goal Scheduling & Delay Execution Service."""

from __future__ import annotations

from threading import RLock

from backend.goals.goal_models import Goal
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GoalScheduler:
    """Manages scheduled background goals."""

    def __init__(self) -> None:
        self._scheduled: list[Goal] = []
        self._lock = RLock()

    def schedule_goal(self, goal: Goal) -> None:
        """Schedule a goal for delayed background execution."""
        with self._lock:
            self._scheduled.append(goal)
            logger.info("Goal %s scheduled for background execution.", goal.goal_id)

    def list_scheduled(self) -> list[Goal]:
        with self._lock:
            return list(self._scheduled)
