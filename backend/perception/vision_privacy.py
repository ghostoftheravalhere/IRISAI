"""Vision Privacy & Sensitivity Filter."""

from __future__ import annotations

import re
from typing import Sequence

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Default blacklisted window titles / process names
_DEFAULT_BLACKLIST = (
    "1password",
    "bitwarden",
    "keepass",
    "dashlane",
    "lastpass",
    "private browsing",
    "incognito",
    "bank",
)

# Common PII regex patterns
_CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PASSWORD_PATTERN = re.compile(r"(?i)\b(?:password|passcode|secret|api[_-]?key)\s*[:=]\s*\S+")


class VisionPrivacyFilter:
    """Filter to ensure screen capture and OCR respect user privacy policies."""

    def __init__(self, blacklisted_apps: Sequence[str] | None = None, enabled: bool = True) -> None:
        self._blacklisted_apps = set(app.lower() for app in (blacklisted_apps or _DEFAULT_BLACKLIST))
        self._enabled = enabled
        self._paused = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def paused(self) -> bool:
        return self._paused

    def set_paused(self, paused: bool) -> None:
        """Pause or resume visual capture."""
        self._paused = paused
        logger.info("Vision privacy capture pause state set to %s", paused)

    def is_window_allowed(self, window_title: str | None) -> bool:
        """Return True if capturing the given window title is permitted."""
        if not self._enabled or self._paused:
            return False

        if not window_title:
            return True

        title_lower = window_title.strip().lower()
        for blocked in self._blacklisted_apps:
            if blocked in title_lower:
                logger.warning("Vision capture blocked by privacy blacklist: '%s'", window_title)
                return False
        return True

    def sanitize_ocr_text(self, text: str) -> str:
        """Redact sensitive PII data from extracted OCR text."""
        if not text or not self._enabled:
            return text

        redacted = _CREDIT_CARD_PATTERN.sub("[REDACTED CARD]", text)
        redacted = _SSN_PATTERN.sub("[REDACTED SSN]", redacted)
        redacted = _PASSWORD_PATTERN.sub("[REDACTED SECRET]", redacted)
        return redacted
