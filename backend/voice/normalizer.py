"""Data-driven transcript normalization service for voice recognition near-misses."""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class NormalizationRule:
    """Rule definition mapping a regular expression pattern to a replacement string."""

    rule_id: str
    pattern: re.Pattern[str]
    replacement: str


class TranscriptNormalizer:
    """Correct consistent speech recognition near-misses prior to intent parsing."""

    def __init__(self, rules: list[NormalizationRule] | None = None) -> None:
        self._rules = rules if rules is not None else self._default_rules()

    def normalize(self, text: str | None) -> str:
        """Apply data-driven normalization rules and return the normalized transcript."""
        raw = text or ""
        if not raw.strip():
            return raw

        normalized = raw
        applied_rule_id: str | None = None

        for rule in self._rules:
            if rule.pattern.search(normalized):
                normalized = rule.pattern.sub(rule.replacement, normalized)
                applied_rule_id = rule.rule_id

        if applied_rule_id is not None:
            logger.info("Normalizer:")
            logger.info("- raw transcript: %s", raw)
            logger.info("- normalized transcript: %s", normalized)
            logger.info("- applied rule: %s", applied_rule_id)
        else:
            logger.debug("Normalizer: no rule applied for '%s'", raw)

        return normalized

    @staticmethod
    def _default_rules() -> list[NormalizationRule]:
        """Data-driven normalization rules for Whisper substitutions."""
        return [
            NormalizationRule(
                rule_id="OPEN_CHROME_CURL",
                pattern=re.compile(r"\b(open|launch|start)\s+curl\b", re.IGNORECASE),
                replacement=r"\1 chrome",
            ),
            NormalizationRule(
                rule_id="OPEN_CHROME_CROW",
                pattern=re.compile(r"\b(open|launch|start)\s+crow\b", re.IGNORECASE),
                replacement=r"\1 chrome",
            ),
            NormalizationRule(
                rule_id="OPEN_CHROME_CHROM",
                pattern=re.compile(r"\b(open|launch|start)\s+chrom\b", re.IGNORECASE),
                replacement=r"\1 chrome",
            ),
            NormalizationRule(
                rule_id="COMPOUND_NOTEPAD",
                pattern=re.compile(r"\bnote\s+pad\b", re.IGNORECASE),
                replacement="notepad",
            ),
            NormalizationRule(
                rule_id="COMPOUND_SCREENSHOT",
                pattern=re.compile(r"\bscreen\s+shot\b", re.IGNORECASE),
                replacement="screenshot",
            ),
        ]
