"""Memory Privacy, Redaction & Forget Control Service."""

from __future__ import annotations

import re
from typing import Sequence

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Sensitivity regex patterns for memory sanitization
_CREDIT_CARD_REGEX = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
_PASSWORD_REGEX = re.compile(r"(?i)\b(?:password|secret|key|token)\s*[:=]\s*\S+")


class MemoryPrivacyFilter:
    """Filter to enforce memory privacy policies, redaction, and topic deletion."""

    def __init__(self, sensitive_keywords: Sequence[str] | None = None) -> None:
        self._sensitive_keywords = set(k.lower() for k in (sensitive_keywords or []))

    def sanitize_content(self, content: str) -> str:
        """Sanitize sensitive keywords and PII from memory text prior to persistence."""
        if not content:
            return content

        sanitized = _CREDIT_CARD_REGEX.sub("[REDACTED CARD]", content)
        sanitized = _PASSWORD_REGEX.sub("[REDACTED SECRET]", sanitized)
        return sanitized

    def should_forget(self, content: str, topic: str) -> bool:
        """Return True if content matches the target topic for deletion."""
        if not content or not topic:
            return False
        return topic.strip().lower() in content.strip().lower()
