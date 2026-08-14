"""Workflow Optimizer for Redundant Action Merging & Multi-App Optimization."""

from __future__ import annotations

from backend.brain.workflow import TaskPlan, WorkflowStep
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class WorkflowOptimizer:
    """Optimizes workflow plans by merging redundant launches and reusing open windows."""

    def optimize_plan(self, plan: TaskPlan, active_apps: list[str] | None = None) -> TaskPlan:
        """Optimize TaskPlan steps to eliminate redundant application launches."""
        active = set(a.lower() for a in (active_apps or []))
        optimized_steps: list[WorkflowStep] = []
        seen_launches: set[str] = set()

        for step in plan.steps:
            intent = step.intent.upper()
            target = (step.target or "").lower()

            if intent in ("OPEN_APPLICATION", "OPEN_CHROME", "OPEN_NOTEPAD"):
                if target in active or target in seen_launches:
                    logger.info("WorkflowOptimizer skipped redundant launch for app '%s'", target)
                    continue
                seen_launches.add(target)

            optimized_steps.append(step)

        logger.info(
            "WorkflowOptimizer optimized plan '%s': %d -> %d steps",
            plan.name,
            len(plan.steps),
            len(optimized_steps),
        )

        return TaskPlan(
            name=f"{plan.name} (Optimized)",
            steps=optimized_steps,
            session_id=plan.session_id,
            plan_id=plan.plan_id,
        )
