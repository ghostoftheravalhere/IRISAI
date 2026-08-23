"""Central Agentic Goal Manager Coordinator Subsystem."""

from __future__ import annotations

from threading import RLock
from typing import Sequence

from backend.brain.workflow import WorkflowEngine
from backend.core.events.bus import EventBus
from backend.goals.goal_events import GoalCreatedEvent, GoalStatusChangedEvent
from backend.goals.goal_executor import GoalExecutor
from backend.goals.goal_models import Goal, GoalProgress, GoalStatus
from backend.goals.goal_monitor import GoalMonitor
from backend.goals.goal_planner import GoalPlanner
from backend.goals.goal_scheduler import GoalScheduler
from backend.goals.goal_state_machine import GoalStateMachine
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GoalManager:
    """Central Goal Manager coordinating Planner, Executor, Monitor, State Machine, and Scheduler."""

    def __init__(
        self,
        workflow_engine: WorkflowEngine,
        event_bus: EventBus | None = None,
        enabled: bool = True,
    ) -> None:
        self._workflow_engine = workflow_engine
        self._event_bus = event_bus
        self._planner = GoalPlanner()
        self._executor = GoalExecutor(workflow_engine=workflow_engine, event_bus=event_bus)
        self._monitor = GoalMonitor()
        self._scheduler = GoalScheduler()
        self._goals: dict[str, Goal] = {}
        self._enabled = enabled
        self._lock = RLock()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def create_goal(self, name: str) -> Goal:
        """Create and register a new high-level user goal."""
        with self._lock:
            goal = Goal(name=name, status=GoalStatus.CREATED)
            self._goals[goal.goal_id] = goal

            if self._event_bus:
                self._event_bus.publish(GoalCreatedEvent(goal_id=goal.goal_id, name=goal.name))

            logger.info("Created Agentic Goal: '%s' (id=%s)", name, goal.goal_id)
            return goal

    def plan_and_execute(self, goal_id: str) -> bool:
        """Decompose and execute an Agentic Goal."""
        with self._lock:
            goal = self._goals.get(goal_id)
            if not goal:
                logger.error("Goal %s not found for execution.", goal_id)
                return False

            GoalStateMachine.transition(goal, GoalStatus.PLANNING)
            self._planner.plan_goal(goal)

            return self._executor.execute_goal(goal)

    def pause_goal(self, goal_id: str) -> bool:
        """Pause execution of an active goal."""
        with self._lock:
            goal = self._goals.get(goal_id)
            if goal and goal.status == GoalStatus.EXECUTING:
                GoalStateMachine.transition(goal, GoalStatus.WAITING)
                return True
            return False

    def resume_goal(self, goal_id: str) -> bool:
        """Resume execution of a waiting goal."""
        with self._lock:
            goal = self._goals.get(goal_id)
            if goal and goal.status == GoalStatus.WAITING:
                return self._executor.execute_goal(goal)
            return False

    def cancel_goal(self, goal_id: str) -> bool:
        """Cancel execution of a goal."""
        with self._lock:
            goal = self._goals.get(goal_id)
            if goal:
                GoalStateMachine.transition(goal, GoalStatus.CANCELLED)
                return True
            return False

    def get_goal(self, goal_id: str) -> Goal | None:
        with self._lock:
            return self._goals.get(goal_id)

    def list_goals(self) -> list[Goal]:
        with self._lock:
            return list(self._goals.values())

    def get_progress(self, goal_id: str) -> GoalProgress | None:
        with self._lock:
            goal = self._goals.get(goal_id)
            if not goal:
                return None
            return self._monitor.get_progress(goal)
