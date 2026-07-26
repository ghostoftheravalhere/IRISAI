"""Intent-first voice command parsing with verb priority and fuzzy targets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class VoiceIntentType(str, Enum):
    """Supported voice automation intents."""

    OPEN_APPLICATION = "OPEN_APPLICATION"
    CLOSE_APPLICATION = "CLOSE_APPLICATION"
    # Legacy aliases kept for dispatcher/tests compatibility.
    OPEN_CHROME = "OPEN_CHROME"
    OPEN_NOTEPAD = "OPEN_NOTEPAD"
    SCROLL_DOWN = "SCROLL_DOWN"
    SCROLL_UP = "SCROLL_UP"
    VOLUME_UP = "VOLUME_UP"
    VOLUME_DOWN = "VOLUME_DOWN"
    MUTE = "MUTE"
    COPY = "COPY"
    PASTE = "PASTE"
    SELECT_ALL = "SELECT_ALL"
    MINIMIZE_WINDOW = "MINIMIZE_WINDOW"
    CLOSE_WINDOW = "CLOSE_WINDOW"
    TAKE_SCREENSHOT = "TAKE_SCREENSHOT"
    NO_INTENT = "NO_INTENT"


@dataclass(frozen=True)
class VoiceIntent:
    """Parsed command intent from recognized speech."""

    intent: VoiceIntentType
    text: str
    confidence: float = 0.0
    target: str | None = None


class IntentParserService:
    """Convert speech transcripts into desktop intents.

    Matching is verb-first: the action word decides the intent family before any
    application name is considered. This prevents ``Close Chrome`` from fuzzy-
    matching ``Open Chrome``.
    """

    _FUZZY_MIN_RATIO = 0.82
    _TARGET_FUZZY_MIN_RATIO = 0.75

    _OPEN_VERBS = ("open", "launch", "start", "opened")
    _CLOSE_VERBS = ("close", "quit", "exit", "kill", "closed")
    _MINIMIZE_VERBS = ("minimize", "minimise")

    _APP_TARGETS: dict[str, tuple[str, ...]] = {
        "chrome": ("chrome", "google chrome", "chrom", "crow", "browser"),
        "notepad": ("notepad", "note pad", "editor"),
        "edge": ("edge", "microsoft edge", "ms edge", "msedge"),
        "window": ("window", "app", "application", "the window"),
    }

    _PHRASE_COMMANDS: dict[VoiceIntentType, tuple[str, ...]] = {
        VoiceIntentType.SCROLL_DOWN: ("scroll down", "go down", "move down", "scrolldown"),
        VoiceIntentType.SCROLL_UP: ("scroll up", "go up", "move up", "scrollup"),
        VoiceIntentType.VOLUME_UP: (
            "volume up",
            "increase volume",
            "turn volume up",
            "louder",
        ),
        VoiceIntentType.VOLUME_DOWN: (
            "volume down",
            "decrease volume",
            "turn volume down",
            "quieter",
        ),
        VoiceIntentType.MUTE: ("mute", "mute volume", "mute sound", "silence", "unmute"),
        VoiceIntentType.COPY: ("copy", "copy text", "copy selection", "copy that"),
        VoiceIntentType.PASTE: ("paste", "paste text", "paste that"),
        VoiceIntentType.SELECT_ALL: ("select all", "select everything"),
        VoiceIntentType.TAKE_SCREENSHOT: (
            "take screenshot",
            "screenshot",
            "capture screen",
            "screen shot",
            "take a screenshot",
        ),
    }

    def parse(self, transcript: str | None) -> VoiceIntent:
        """Parse a transcript using verb-first intent resolution."""
        text = transcript or ""
        normalized = self._normalize(text)
        if not normalized:
            return VoiceIntent(intent=VoiceIntentType.NO_INTENT, text=text)

        verb_intent = self._parse_verb_first(normalized, text)
        if verb_intent is not None:
            logger.info(
                "Voice intent verb-first: %s target=%s",
                verb_intent.intent.value,
                verb_intent.target,
            )
            return verb_intent

        for intent, phrases in self._PHRASE_COMMANDS.items():
            if normalized in phrases:
                return VoiceIntent(intent=intent, text=text, confidence=1.0)

        for intent, phrases in self._PHRASE_COMMANDS.items():
            if any(self._contains_phrase(normalized, phrase) for phrase in phrases):
                return VoiceIntent(intent=intent, text=text, confidence=0.85)

        fuzzy = self._fuzzy_match_phrases(normalized, text)
        if fuzzy is not None:
            return fuzzy

        logger.debug("No voice intent matched transcript: %s", text)
        return VoiceIntent(intent=VoiceIntentType.NO_INTENT, text=text)

    def _parse_verb_first(self, normalized: str, original: str) -> VoiceIntent | None:
        """Resolve open/close/minimize intents from the leading action verb."""
        tokens = normalized.split()
        if not tokens:
            return None

        verb = self._match_verb(tokens[0])
        if verb is None:
            # Allow "please close chrome" after filler stripping; also "can you open…"
            for index, token in enumerate(tokens[:3]):
                verb = self._match_verb(token)
                if verb is not None:
                    tokens = tokens[index:]
                    break
        if verb is None:
            return None

        remainder = " ".join(tokens[1:]).strip()
        target = self._resolve_target(remainder) if remainder else None

        if verb == "open":
            if target == "chrome":
                return VoiceIntent(
                    intent=VoiceIntentType.OPEN_CHROME,
                    text=original,
                    confidence=0.95,
                    target="chrome",
                )
            if target == "notepad":
                return VoiceIntent(
                    intent=VoiceIntentType.OPEN_NOTEPAD,
                    text=original,
                    confidence=0.95,
                    target="notepad",
                )
            if target is not None:
                return VoiceIntent(
                    intent=VoiceIntentType.OPEN_APPLICATION,
                    text=original,
                    confidence=0.9,
                    target=target,
                )
            return None

        if verb == "close":
            # Any close + app/window maps to close-application semantics.
            resolved_target = target or "window"
            return VoiceIntent(
                intent=VoiceIntentType.CLOSE_APPLICATION,
                text=original,
                confidence=0.95 if target else 0.85,
                target=resolved_target,
            )

        if verb == "minimize":
            return VoiceIntent(
                intent=VoiceIntentType.MINIMIZE_WINDOW,
                text=original,
                confidence=0.95,
                target=target or "window",
            )

        return None

    def _match_verb(self, token: str) -> str | None:
        """Map a token onto a canonical action verb."""
        if token in self._OPEN_VERBS or self._fuzzy_token(token, self._OPEN_VERBS):
            return "open"
        if token in self._CLOSE_VERBS or self._fuzzy_token(token, self._CLOSE_VERBS):
            return "close"
        if token in self._MINIMIZE_VERBS or self._fuzzy_token(token, self._MINIMIZE_VERBS):
            return "minimize"
        return None

    def _resolve_target(self, remainder: str) -> str | None:
        """Resolve an application/window target from the words after the verb."""
        if not remainder:
            return None

        for target, synonyms in self._APP_TARGETS.items():
            if remainder in synonyms or any(self._contains_phrase(remainder, syn) for syn in synonyms):
                return target

        best_target: str | None = None
        best_ratio = 0.0
        for target, synonyms in self._APP_TARGETS.items():
            for synonym in synonyms:
                ratio = SequenceMatcher(None, remainder, synonym).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_target = target

        if best_target is not None and best_ratio >= self._TARGET_FUZZY_MIN_RATIO:
            return best_target
        return None

    def _fuzzy_match_phrases(self, normalized: str, original: str) -> VoiceIntent | None:
        """Fuzzy-match only non open/close phrase commands (never cross verbs)."""
        best_intent: VoiceIntentType | None = None
        best_ratio = 0.0

        for intent, phrases in self._PHRASE_COMMANDS.items():
            for phrase in phrases:
                ratio = SequenceMatcher(None, normalized, phrase).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_intent = intent

        if best_intent is None or best_ratio < self._FUZZY_MIN_RATIO:
            return None
        return VoiceIntent(intent=best_intent, text=original, confidence=best_ratio)

    @staticmethod
    def _fuzzy_token(token: str, candidates: tuple[str, ...]) -> bool:
        """Return whether a token is a close synonym of any candidate verb."""
        for candidate in candidates:
            if SequenceMatcher(None, token, candidate).ratio() >= 0.86:
                return True
        return False

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize speech text for stable rule matching."""
        normalized = text.lower().strip()
        normalized = re.sub(r"\b(um|uh|please|okay|ok|hey|iris|can you|could you)\b", " ", normalized)
        normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _contains_phrase(text: str, phrase: str) -> bool:
        """Match full command phrases without partial word collisions."""
        return re.search(rf"\b{re.escape(phrase)}\b", text) is not None
