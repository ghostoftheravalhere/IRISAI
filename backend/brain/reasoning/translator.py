"""Plan Translator and Plan Validator for LLM response parsing and hallucination prevention."""

from __future__ import annotations

import json
import re
from typing import Any

from backend.brain.skills.registry import SkillRegistry
from backend.brain.workflow import TaskPlan, WorkflowStep
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class PlanTranslator:
    """Parses raw LLM string/JSON responses into candidate TaskPlan objects."""

    @staticmethod
    def translate(raw_output: str) -> TaskPlan | None:
        """Extract and parse candidate TaskPlan from raw output string."""
        if not raw_output or not raw_output.strip():
            return None

        # Clean JSON block if wrapped in markdown ```json ... ```
        cleaned = raw_output.strip()
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1)

        try:
            data = json.loads(cleaned)
            if not isinstance(data, dict):
                return None

            plan_name = data.get("name", "LLM Generated Plan")
            raw_steps = data.get("steps", [])
            if not isinstance(raw_steps, list) or not raw_steps:
                return None

            steps: list[WorkflowStep] = []
            for s in raw_steps:
                if isinstance(s, dict) and "intent" in s:
                    steps.append(
                        WorkflowStep(
                            intent=s["intent"],
                            target=s.get("target"),
                            params=s.get("params", {}),
                            rollback_intent=s.get("rollback_intent"),
                        )
                    )

            if not steps:
                return None

            return TaskPlan(name=plan_name, steps=steps)
        except Exception as exc:
            logger.warning("Failed to translate raw LLM response to TaskPlan: %s", exc)
            return None


class PlanValidator:
    """Validates candidate TaskPlan against registered Skill capabilities to prevent hallucinations."""

    @staticmethod
    def validate_plan(plan: TaskPlan, skill_registry: SkillRegistry) -> tuple[bool, str]:
        """Validate every step in candidate plan against registered Skills."""
        if not plan or not plan.steps:
            return False, "Plan is empty or contains no execution steps."

        for idx, step in enumerate(plan.steps):
            skill = skill_registry.find_skill_for_intent(step.intent)
            if not skill:
                return False, f"Plan rejected: step {idx} intent '{step.intent}' is not registered in SkillRegistry."

        return True, "TaskPlan successfully validated against registered Skills."
