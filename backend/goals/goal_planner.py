"""High-Level Goal Decomposition & TaskPlan Generator."""

from __future__ import annotations

from backend.brain.workflow import TaskPlan, WorkflowStep
from backend.goals.goal_models import Goal
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GoalPlanner:
    """Decomposes high-level user goal prompts into executable TaskPlan sub-workflows."""

    def plan_goal(self, goal: Goal) -> list[TaskPlan]:
        """Decompose a high-level goal into an ordered sequence of sub-plans."""
        prompt = goal.name.strip().lower()
        sub_plans: list[TaskPlan] = []

        if "study" in prompt or "prepare" in prompt:
            p1 = TaskPlan(
                name="Open Search Engine for Study Material",
                steps=[
                    WorkflowStep(intent="OPEN_APPLICATION", target="chrome"),
                    WorkflowStep(intent="WAIT_FOR_WINDOW", target="chrome", params={"timeout_sec": 3.0}),
                    WorkflowStep(intent="ACTIVATE_WINDOW", target="chrome"),
                    WorkflowStep(intent="VERIFY_WINDOW_ACTIVE", target="chrome"),
                    WorkflowStep(intent="HOTKEY", target="chrome", params={"keys": ["ctrl", "l"]}),
                    WorkflowStep(intent="TYPE_TEXT", target="chrome", params={"text": "DDCET syllabus", "query": "DDCET syllabus"}),
                    WorkflowStep(intent="PRESS_KEY", target="chrome", params={"key": "enter"}),
                ],
            )
            p2 = TaskPlan(
                name="Configure System Audio Volume",
                steps=[
                    WorkflowStep(intent="OPEN_APPLICATION", target="settings"),
                    WorkflowStep(intent="WAIT_FOR_WINDOW", target="settings", params={"timeout_sec": 3.0}),
                ],
            )
            sub_plans.extend([p1, p2])
        elif "clean" in prompt or "downloads" in prompt:
            p1 = TaskPlan(
                name="Inspect Downloads Folder",
                steps=[
                    WorkflowStep(intent="OPEN_APPLICATION", target="explorer"),
                ],
            )
            sub_plans.append(p1)
        else:
            # Generic fallback sub-plan
            p1 = TaskPlan(
                name=f"Execute Goal '{goal.name}'",
                steps=[
                    WorkflowStep(intent="OPEN_APPLICATION", target="chrome"),
                ],
            )
            sub_plans.append(p1)

        goal.sub_plans = sub_plans
        logger.info("GoalPlanner decomposed '%s' into %d sub-plans", goal.name, len(sub_plans))
        return sub_plans
