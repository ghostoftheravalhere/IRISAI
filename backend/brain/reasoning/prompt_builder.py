"""Prompt Builder for skill-bound LLM planning prompts."""

from __future__ import annotations

import json
from typing import Any

from backend.brain.skills.base import SkillDescriptor


class PromptBuilder:
    """Formats system instructions, skill catalogs, and session history into structured prompts."""

    @staticmethod
    def build_prompt(
        user_command: str,
        skill_descriptors: list[SkillDescriptor],
        context: dict[str, Any] | None = None,
    ) -> str:
        """Construct a skill-bound LLM prompt instructing JSON plan generation."""
        capabilities: list[str] = []
        for desc in skill_descriptors:
            capabilities.extend(desc.capabilities)

        capability_list = sorted(list(set(capabilities)))

        prompt_dict = {
            "instruction": "You are IRIS AI Task Planner. Output ONLY valid JSON containing a 'name' and 'steps' list.",
            "allowed_intents": capability_list,
            "session_context": context or {},
            "user_command": user_command,
        }

        return json.dumps(prompt_dict, indent=2)
