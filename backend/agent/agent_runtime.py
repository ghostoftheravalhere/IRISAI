"""Central Autonomous Agent Runtime Subsystem."""

from __future__ import annotations

from threading import RLock

from backend.agent.agent_loop import AgentLoop
from backend.agent.agent_models import AgentLoopPhase
from backend.brain.workflow import TaskPlan, WorkflowEngine
from backend.core.events.bus import EventBus
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class AgentRuntime:
    """Central Autonomous Agent Runtime Coordinator."""

    def __init__(
        self,
        workflow_engine: WorkflowEngine,
        event_bus: EventBus | None = None,
        enabled: bool = True,
    ) -> None:
        self._workflow_engine = workflow_engine
        self._event_bus = event_bus
        self._loop = AgentLoop(workflow_engine=workflow_engine)
        self._enabled = enabled
        self._lock = RLock()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def phase(self) -> AgentLoopPhase:
        return self._loop.phase

    def run_agent_goal(self, goal_name: str, plan: TaskPlan) -> bool:
        """Launch autonomous agent loop for a goal and plan."""
        with self._lock:
            if not self._enabled:
                return False

            logger.info("AgentRuntime launched goal: '%s'", goal_name)
            return self._loop.run_cycle(plan)
