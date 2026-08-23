"""Incremental Reasoner & Partial Intent Predictor."""

from __future__ import annotations

import re

from backend.nlu.multi_intent_parser import MultiIntentParser
from backend.utils.logger import get_logger
from backend.voice.streaming_models import PartialIntent

logger = get_logger(__name__)

# Self-correction phrases ("actually Edge", "no wait Notepad")
_CORRECTION_REGEX = re.compile(r"\b(?:actually|no wait|instead|correction)\s+(.+)", re.IGNORECASE)


class IncrementalReasoner:
    """Predicts partial intents from partial transcripts and detects mid-utterance self-corrections."""

    def __init__(self, parser: MultiIntentParser | None = None) -> None:
        self._parser = parser or MultiIntentParser()

    def predict_partial(self, partial_text: str) -> PartialIntent:
        """Predict tentative intent from streaming partial transcript."""
        if not partial_text or not partial_text.strip():
            return PartialIntent(intent_name="NO_INTENT", is_stable=False)

        corrected_text = partial_text
        corr_m = _CORRECTION_REGEX.search(partial_text)
        if corr_m:
            correction_part = corr_m.group(1).strip()
            corrected_text = f"Open {correction_part}"
            logger.info("IncrementalReasoner detected self-correction: '%s' -> '%s'", partial_text, corrected_text)

        nlu_res = self._parser.parse_utterance(corrected_text)

        is_stable = len(partial_text.split()) >= 2
        return PartialIntent(
            intent_name=nlu_res.intent_name,
            target=nlu_res.target,
            query=nlu_res.query,
            confidence=nlu_res.confidence,
            is_stable=is_stable,
        )
