"""Post-Action Reflection Engine Service."""

from __future__ import annotations

from backend.agent.agent_models import AgentObservation, ReflectionReport
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ReflectionEngine:
    """Evaluates post-action visual/state deltas and suggests plan continuation or replanning."""

    def reflect(self, step_name: str, step_verified: bool, obs_before: AgentObservation, obs_after: AgentObservation) -> ReflectionReport:
        """Analyze pre/post observations and generate a ReflectionReport."""
        delta = obs_before.active_app != obs_after.active_app or obs_before.visible_text != obs_after.visible_text

        report = ReflectionReport(
            step_name=step_name,
            success=step_verified,
            delta_observed=delta or step_verified,
            continue_plan=step_verified,
            suggested_replan=not step_verified,
            notes="Step execution verified successfully." if step_verified else "Step verification failed, replan recommended.",
        )
        logger.info("ReflectionEngine reflected on '%s': continue=%s", step_name, report.continue_plan)
        return report
