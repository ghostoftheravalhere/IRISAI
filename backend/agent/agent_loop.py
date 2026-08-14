"""Iterative Autonomous Agent Loop Execution Controller."""

from __future__ import annotations

import time

from backend.agent.agent_models import AgentLoopPhase, AgentObservation
from backend.agent.observation_engine import ObservationEngine
from backend.agent.recovery_policy import RecoveryPolicy
from backend.agent.reflection_engine import ReflectionEngine
from backend.agent.verification_engine import VerificationEngine
from backend.brain.workflow import TaskPlan, WorkflowEngine
from backend.utils.logger import get_logger

logger = get_logger(__name__)


from backend.brain.dry_run_engine import DryRunEngine
from backend.brain.execution_planner import ExecutionPlanner
from backend.brain.risk_assessment import RiskAssessmentEngine


class AgentLoop:
    """Coordinates autonomous execution loops (OBSERVE -> REASON -> PLAN -> RISK_ANALYSIS -> DRY_RUN -> EXECUTE -> VERIFY -> REFLECT)."""

    def __init__(
        self,
        workflow_engine: WorkflowEngine,
        observation_engine: ObservationEngine | None = None,
        verification_engine: VerificationEngine | None = None,
        reflection_engine: ReflectionEngine | None = None,
    ) -> None:
        self._workflow_engine = workflow_engine
        self._observer = observation_engine or ObservationEngine()
        self._verifier = verification_engine or VerificationEngine()
        self._reflector = reflection_engine or ReflectionEngine()
        self._execution_planner = ExecutionPlanner()
        self._risk_engine = RiskAssessmentEngine()
        self._dry_run_engine = DryRunEngine()
        self._recovery = RecoveryPolicy()
        self._phase = AgentLoopPhase.FINISHED

    @property
    def phase(self) -> AgentLoopPhase:
        return self._phase

    def run_cycle(self, plan: TaskPlan) -> bool:
        """Run a single autonomous cycle through all loop phases."""
        self._phase = AgentLoopPhase.OBSERVE
        obs_before = self._observer.capture_observation()

        self._phase = AgentLoopPhase.REASON
        self._phase = AgentLoopPhase.PLAN

        # Pre-execution intelligence phase: Risk Analysis & Dry Run Simulation
        exec_plan = self._execution_planner.analyze_plan(plan)
        risk_report = self._risk_engine.evaluate_plan(plan)
        dry_run_res = self._dry_run_engine.simulate(plan)

        self._phase = AgentLoopPhase.EXECUTE
        success = self._workflow_engine.execute_plan(plan)

        self._phase = AgentLoopPhase.VERIFY
        obs_after = self._observer.capture_observation()
        verify_target = plan.steps[0].target if (plan.steps and plan.steps[0].target) else plan.name
        verified = self._verifier.verify_step(verify_target, obs_after) and success

        self._phase = AgentLoopPhase.REFLECT
        report = self._reflector.reflect(plan.name, verified, obs_before, obs_after)

        if report.continue_plan:
            self._phase = AgentLoopPhase.FINISHED
            return True

        self._phase = AgentLoopPhase.RECOVER
        recovery_action = self._recovery.handle_failure(retry_count=1)
        logger.warning("AgentLoop recovery action: %s", recovery_action)
        self._phase = AgentLoopPhase.FINISHED
        return False
