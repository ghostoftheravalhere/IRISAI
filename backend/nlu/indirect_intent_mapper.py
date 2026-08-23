"""Indirect & Conversational Intent Mapper."""

from __future__ import annotations

import re

from backend.nlu.nlu_models import ParsedNLUIntent
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_INDIRECT_PATTERNS = {
    r"\bi'm bored\b": ("OPEN_APPLICATION", "spotify", None),
    r"\bi am bored\b": ("OPEN_APPLICATION", "spotify", None),
    r"\bi'm studying\b": ("OPEN_APPLICATION", "chrome", "DDCET syllabus"),
    r"\bmy laptop is slow\b": ("OPEN_APPLICATION", "taskmgr", None),
    r"\blet's code\b": ("OPEN_APPLICATION", "vscode", None),
}


class IndirectIntentMapper:
    """Maps indirect conversational phrases to actionable system intents."""

    def map_indirect(self, text: str) -> ParsedNLUIntent | None:
        """Check if utterance matches indirect conversational patterns."""
        cleaned = text.strip().lower()
        for pattern, (intent_name, target, query) in _INDIRECT_PATTERNS.items():
            if re.search(pattern, cleaned, re.IGNORECASE):
                logger.info("IndirectIntentMapper matched '%s' -> %s(%s)", text, intent_name, target)
                return ParsedNLUIntent(
                    intent_name=intent_name,
                    target=target,
                    query=query,
                    confidence=0.90,
                    is_indirect=True,
                )
        return None
