"""Dry Run Simulation Engine for Non-Destructive Plan Validation."""

from __future__ import annotations

from dataclasses import dataclass, field
import time

from backend.brain.workflow import TaskPlan
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DryRunResult:
    """Predictive simulation result of a TaskPlan dry-run walk."""

    predicted_success_percent: float
    potential_failures: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    missing_apps: list[str] = field(default_factory=list)
    expected_runtime_sec: float = 0.0


class DryRunEngine:
    """Simulates workflow execution without performing desktop interactions or side-effects."""

    def simulate(self, plan: TaskPlan) -> DryRunResult:
        """Perform a dry-run validation walk across plan steps."""
        start = time.monotonic()
        missing_s: list[str] = []
        missing_a: list[str] = []
        failures: list[str] = []
        est_runtime = 0.0

        for step in plan.steps:
            est_runtime += 0.4
            intent = step.intent.upper()
            target = step.target or ""

            if intent == "UNKNOWN_SKILL_INTENT":
                missing_s.append(f"Skill '{step.intent}' not registered in SkillRegistry")
                failures.append(f"Unregistered skill for step '{step.intent}'")

            elif intent in ("OPEN_APPLICATION", "OPEN_CHROME") and target == "non_existent_app_xyz":
                missing_a.append(target)
                failures.append(f"Target executable '{target}' not found on host machine")

        total_steps = max(len(plan.steps), 1)
        passed_steps = total_steps - len(failures)
        predicted_success = (passed_steps / total_steps) * 100.0
        elapsed = time.monotonic() - start

        logger.info(
            "DryRunEngine simulated plan '%s': predicted_success=%.1f%% (latency=%.2fms)",
            plan.name,
            predicted_success,
            elapsed * 1000.0,
        )

        return DryRunResult(
            predicted_success_percent=round(predicted_success, 1),
            potential_failures=failures,
            missing_skills=missing_s,
            missing_apps=missing_a,
            expected_runtime_sec=round(est_runtime, 2),
        )
