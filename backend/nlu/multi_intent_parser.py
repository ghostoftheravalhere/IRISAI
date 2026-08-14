"""Multi-Intent Compound Utterance Parser Engine."""

from __future__ import annotations

import re

from backend.nlu.entity_extractor import EntityExtractor
from backend.nlu.indirect_intent_mapper import IndirectIntentMapper
from backend.nlu.nlu_models import ParsedNLUIntent
from backend.nlu.synonym_engine import SynonymEngine
from backend.utils.logger import get_logger
from backend.voice.command_parser import IntentParserService, VoiceIntentType

logger = get_logger(__name__)


class MultiIntentParser:
    """Parses compound utterances ('Open Chrome and search ChatGPT') into sub-intents."""

    def __init__(self) -> None:
        self._synonym = SynonymEngine()
        self._entity_extractor = EntityExtractor()
        self._indirect_mapper = IndirectIntentMapper()
        self._base_parser = IntentParserService()

    def parse_utterance(self, text: str) -> ParsedNLUIntent:
        """Parse raw utterance into single or compound ParsedNLUIntent."""
        if not text:
            return ParsedNLUIntent(intent_name="UNKNOWN", confidence=0.0)

        # Step 1: Check indirect conversational mapping
        indirect_res = self._indirect_mapper.map_indirect(text)
        if indirect_res:
            return indirect_res

        # Step 2: Normalize synonyms
        normalized = self._synonym.normalize(text)

        # Step 3: Check compound conjunctions ("and", "then", "after that")
        parts = re.split(r"\b(?:and|then|after that)\b", normalized, flags=re.IGNORECASE)
        if len(parts) > 1:
            sub_intents: list[ParsedNLUIntent] = []
            for part in parts:
                p_text = part.strip()
                if p_text:
                    sub = self.parse_utterance(p_text)
                    sub_intents.append(sub)

            first_intent = sub_intents[0].intent_name if sub_intents else "UNKNOWN"
            return ParsedNLUIntent(
                intent_name=first_intent,
                target=sub_intents[0].target if sub_intents else None,
                query=sub_intents[0].query if sub_intents else None,
                sub_intents=sub_intents,
            )

        # Step 4: Base intent parsing & entity extraction
        parsed_voice = self._base_parser.parse(normalized)
        entities = self._entity_extractor.extract_entities(normalized)

        return ParsedNLUIntent(
            intent_name=parsed_voice.intent.value,
            target=parsed_voice.target,
            query=parsed_voice.query,
            confidence=parsed_voice.confidence,
            entities=entities,
        )
