"""Conversational Entity Extractor Service."""

from __future__ import annotations

import re

from backend.nlu.nlu_models import NLUEntity
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_KNOWN_APPS = {"chrome", "edge", "vscode", "notepad", "spotify", "settings", "explorer", "calculator"}


class EntityExtractor:
    """Extracts applications, search queries, URLs, and ordinals from text."""

    def extract_entities(self, text: str) -> list[NLUEntity]:
        """Extract structured entities from conversational text."""
        entities: list[NLUEntity] = []

        tokens = text.lower().split()
        for token in tokens:
            if token in _KNOWN_APPS:
                entities.append(NLUEntity(entity_type="app", value=token, confidence=0.98))

        # Extract search queries after "search" or "for"
        search_m = re.search(r"\bsearch\s+(?:for\s+)?(.+)", text, re.IGNORECASE)
        if search_m:
            query = search_m.group(1).strip()
            # Exclude trailing app targets
            for app in _KNOWN_APPS:
                query = re.sub(r"\b(?:in|on)\s+" + app + r"$", "", query, flags=re.IGNORECASE).strip()
            entities.append(NLUEntity(entity_type="query", value=query, confidence=0.95))

        return entities
