"""Action & Application Synonym Normalizer Engine."""

from __future__ import annotations

import re

from backend.utils.logger import get_logger

logger = get_logger(__name__)

_VERB_SYNONYMS = {
    "launch": "open",
    "start": "open",
    "run": "open",
    "execute": "open",
    "begin": "open",
    "activate": "open",
    "bring up": "open",
    "fire up": "open",
    "let's browse": "open chrome",
    "i want": "open",
    "could you open": "open",
    "please open": "open",
}

_APP_ALIASES = {
    "browser": "chrome",
    "web": "chrome",
    "internet": "chrome",
    "code editor": "vscode",
    "editor": "vscode",
    "vs code": "vscode",
    "music": "spotify",
    "player": "spotify",
    "notes": "notepad",
    "files": "explorer",
    "folders": "explorer",
}


class SynonymEngine:
    """Normalizes action verbs and application aliases in natural language text."""

    def normalize(self, text: str) -> str:
        """Normalize action verbs and app aliases."""
        if not text:
            return text

        normalized = text.strip()

        # Replace phrase prefixes first
        for key, val in _VERB_SYNONYMS.items():
            pattern = re.compile(r"^\b" + re.escape(key) + r"\b", re.IGNORECASE)
            if pattern.search(normalized):
                normalized = pattern.sub(val, normalized)
                break

        # Replace app aliases
        for alias, real_app in _APP_ALIASES.items():
            pattern = re.compile(r"\b" + re.escape(alias) + r"\b", re.IGNORECASE)
            if pattern.search(normalized):
                normalized = pattern.sub(real_app, normalized)

        return normalized.strip()
