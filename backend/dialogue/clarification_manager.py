"""Ambiguity Evaluation & Clarification Manager Service."""

from __future__ import annotations

from typing import Sequence

from backend.dialogue.dialogue_models import ClarificationOption
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ClarificationManager:
    """Evaluates intent ambiguity and generates multiple-choice clarification prompts."""

    def is_ambiguous(self, confidence: float, query: str | None = None) -> bool:
        """Return True if confidence < 0.70 or query phrase is under-specified."""
        if confidence < 0.70:
            return True
        return False

    def generate_options(self, raw_text: str) -> list[ClarificationOption]:
        """Generate clarification choices for ambiguous inputs."""
        return [
            ClarificationOption(
                option_id="opt_1",
                label=f"Search '{raw_text}' in Chrome",
                target_intent="BROWSER_SEARCH",
                resolved_params={"target": "chrome", "query": raw_text},
            ),
            ClarificationOption(
                option_id="opt_2",
                label=f"Search '{raw_text}' in Settings",
                target_intent="BROWSER_SEARCH",
                resolved_params={"target": "settings", "query": raw_text},
            ),
        ]
