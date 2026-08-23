"""Execution Planner Service for Workflow Pre-Flight Analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any

from backend.brain.workflow import TaskPlan, WorkflowStep
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ExecutionPlan:
    """Detailed structural execution breakdown of a TaskPlan prior to dispatch."""

    plan_id: str
    estimated_runtime_sec: float
    required_applications: list[str] = field(default_factory=list)
    required_permissions: list[str] = field(default_factory=list)
    expected_window_changes: list[str] = field(default_factory=list)
    expected_desktop_state: str = "Responsive"
    potential_failures: list[str] = field(default_factory=list)


class ExecutionPlanner:
    """Analyzes a TaskPlan and generates a predictive ExecutionPlan."""

    def analyze_plan(self, plan: TaskPlan) -> ExecutionPlan:
        """Analyze workflow steps and estimate execution parameters."""
        start_time = time.monotonic()
        apps: set[str] = set()
        perms: set[str] = set()
        window_changes: list[str] = []
        failures: list[str] = []
        est_runtime = 0.0

        for step in plan.steps:
            est_runtime += 0.5  # 500ms base step runtime estimate
            intent = step.intent.upper()
            target = step.target or "System"

            if intent in ("OPEN_APPLICATION", "OPEN_CHROME", "OPEN_NOTEPAD"):
                apps.add(target)
                window_changes.append(f"Launch and focus window '{target}'")
                est_runtime += 1.0
            elif intent == "SEARCH_BROWSER":
                apps.add("chrome")
                window_changes.append("Focus address bar and submit query")
                est_runtime += 1.2
            elif "DELETE" in intent or "FORMAT" in intent or "CLOSE" in intent:
                perms.add("ADMINISTRATIVE_FILE_SYSTEM_ACCESS")
                failures.append(f"Action '{intent}' may alter user file system")

        elapsed = time.monotonic() - start_time
        logger.info(
            "ExecutionPlanner analyzed plan '%s' (%d steps, est_runtime=%.2fs, latency=%.2fms)",
            plan.name,
            len(plan.steps),
            est_runtime,
            elapsed * 1000.0,
        )

        return ExecutionPlan(
            plan_id=plan.plan_id,
            estimated_runtime_sec=round(est_runtime, 2),
            required_applications=sorted(list(apps)),
            required_permissions=sorted(list(perms)),
            expected_window_changes=window_changes,
            expected_desktop_state="Responsive Window Context",
            potential_failures=failures,
        )
