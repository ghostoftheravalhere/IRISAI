"""Intent-first voice command parsing with verb priority and fuzzy targets."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum
from typing import Any

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class VoiceIntentType(str, Enum):
    """Supported voice automation intents."""

    OPEN_APPLICATION = "OPEN_APPLICATION"
    OPEN_CHAT = "OPEN_CHAT"
    CLOSE_APPLICATION = "CLOSE_APPLICATION"
    BROWSER_SEARCH = "BROWSER_SEARCH"
    HOTKEY = "HOTKEY"
    TYPE_TEXT = "TYPE_TEXT"
    PRESS_KEY = "PRESS_KEY"
    WAIT_FOR_WINDOW = "WAIT_FOR_WINDOW"
    ACTIVATE_WINDOW = "ACTIVATE_WINDOW"
    VERIFY_WINDOW_ACTIVE = "VERIFY_WINDOW_ACTIVE"
    # Mouse & Selection Intents
    PRIMARY_CLICK = "PRIMARY_CLICK"
    RIGHT_CLICK = "RIGHT_CLICK"
    DOUBLE_CLICK = "DOUBLE_CLICK"
    START_SELECTING = "START_SELECTING"
    STOP_SELECTING = "STOP_SELECTING"
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
    query: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


class IntentParserService:
    """Convert speech transcripts into desktop intents.

    Matching is verb-first: the action word decides the intent family before any
    application name is considered. This prevents ``Close Chrome`` from fuzzy-
    matching ``Open Chrome``.
    """

    _FUZZY_MIN_RATIO = 0.82
    _TARGET_FUZZY_MIN_RATIO = 0.75

    _OPEN_VERBS = ("open", "launch", "start", "opened", "run", "go to", "take me to", "navigate to", "switch to")
    _CLOSE_VERBS = ("close", "quit", "exit", "kill", "closed")
    _MINIMIZE_VERBS = ("minimize", "minimise")

    _APP_TARGETS: dict[str, tuple[str, ...]] = {
        "chrome": ("chrome", "google chrome", "chrom", "crow", "browser"),
        "notepad": ("notepad", "note pad", "editor"),
        "edge": ("edge", "microsoft edge", "ms edge", "msedge"),
        "settings": ("settings", "setting", "windows settings", "system settings", "control panel", "options"),
        "vscode": ("vscode", "vs code", "visual studio code"),
        "spotify": ("spotify", "music player"),
        "taskmgr": ("taskmgr", "task manager"),
        "window": ("window", "app", "application", "the window"),
    }

    _PHRASE_COMMANDS: dict[VoiceIntentType, tuple[str, ...]] = {
        VoiceIntentType.PRIMARY_CLICK: ("click", "left click", "click here", "primary click", "click this", "click it"),
        VoiceIntentType.RIGHT_CLICK: ("right click", "right-click", "do a right click", "rightclick", "context menu", "right click here", "right click it", "right click this"),
        VoiceIntentType.DOUBLE_CLICK: ("double click", "double-click", "doubleclick", "do a double click"),
        VoiceIntentType.START_SELECTING: ("start selecting", "begin selection", "start selection", "start selecting text"),
        VoiceIntentType.STOP_SELECTING: ("stop selecting", "end selection", "stop selection", "finish selecting"),
        VoiceIntentType.SCROLL_DOWN: ("scroll down", "scroll downward", "go down", "move down", "scrolldown"),
        VoiceIntentType.SCROLL_UP: ("scroll up", "scroll upward", "go up", "move up", "scrollup"),
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
        VoiceIntentType.COPY: ("copy", "copy text", "copy selection", "copy that", "copy it", "copy this", "copy the selected text"),
        VoiceIntentType.PASTE: ("paste", "paste text", "paste that", "paste it", "paste here", "paste there"),
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
        logger.info("Parser:")
        logger.info("- normalized text: %s", normalized)
        if not normalized:
            logger.info("- matched rule: empty")
            logger.info("- detectedIntent: %s", VoiceIntentType.NO_INTENT.value)
            return VoiceIntent(intent=VoiceIntentType.NO_INTENT, text=text)

        browser_search = self._parse_browser_search(normalized, text)
        if browser_search is not None:
            logger.info(
                "Voice intent browser search: %s target=%s query=%s",
                browser_search.intent.value,
                browser_search.target,
                browser_search.query,
            )
            logger.info("- matched rule: browser-search")
            logger.info("- detectedIntent: %s", browser_search.intent.value)
            return browser_search

        # Type / write / send text matching
        if normalized.startswith(("type ", "write ", "say ", "send ")):
            parts = text.split(maxsplit=1)
            payload = parts[1] if len(parts) > 1 else ""
            return VoiceIntent(
                intent=VoiceIntentType.TYPE_TEXT,
                text=text,
                confidence=0.90,
                query=payload,
                params={"text": payload},
            )

        # 1. Exact phrase matching (prevents "start selecting" from matching verb "start")
        for intent, phrases in self._PHRASE_COMMANDS.items():
            if normalized in phrases:
                logger.info("- matched rule: exact phrase")
                logger.info("- detectedIntent: %s", intent.value)
                return VoiceIntent(intent=intent, text=text, confidence=1.0)

        # 2. Verb-first matching (open, close, minimize)
        verb_intent = self._parse_verb_first(normalized, text)
        if verb_intent is not None:
            logger.info(
                "Voice intent verb-first: %s target=%s",
                verb_intent.intent.value,
                verb_intent.target,
            )
            logger.info("- matched rule: verb-first")
            logger.info("- detectedIntent: %s", verb_intent.intent.value)
            return verb_intent

        # 3. Contained phrase matching
        for intent, phrases in self._PHRASE_COMMANDS.items():
            if any(self._contains_phrase(normalized, phrase) for phrase in phrases):
                logger.info("- matched rule: contained phrase")
                logger.info("- detectedIntent: %s", intent.value)
                return VoiceIntent(intent=intent, text=text, confidence=0.85)

        fuzzy = self._fuzzy_match_phrases(normalized, text)
        if fuzzy is not None:
            logger.info("- matched rule: fuzzy phrase")
            logger.info("- detectedIntent: %s", fuzzy.intent.value)
            return fuzzy

        logger.debug("No voice intent matched transcript: %s", text)
        logger.info("- matched rule: none")
        logger.info("- detectedIntent: %s", VoiceIntentType.NO_INTENT.value)
        return VoiceIntent(intent=VoiceIntentType.NO_INTENT, text=text)

    @staticmethod
    def _clean_target_phrase(remainder: str) -> str:
        """Strip possessives, determiners, and control/entity suffixes from generic target phrases."""
        clean = remainder.strip()
        clean = re.sub(r"^(my|the|a|an)\s+", "", clean, flags=re.IGNORECASE).strip()
        clean = re.sub(r"\s+(chat|conversation|group|channel|workspace|window|app|tab|folder|document|file)$", "", clean, flags=re.IGNORECASE).strip()
        return clean or remainder

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
        cleaned_rem = self._clean_target_phrase(remainder) if remainder else ""
        target = self._resolve_target(cleaned_rem) if cleaned_rem else None

        if verb == "open":
            is_chat = any(w in remainder.lower() for w in ("chat", "conversation"))
            intent_type = VoiceIntentType.OPEN_CHAT if is_chat else VoiceIntentType.OPEN_APPLICATION

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
                    intent=intent_type,
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
        return remainder

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
        normalized = re.sub(r"\b(um|uh|please|okay|ok|hey|iris|can you|could you|i want to|i'd like to)\b", " ", normalized)
        normalized = re.sub(r"\b(take me to|go to|navigate to|switch to)\b", "open", normalized)
        normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _contains_phrase(text: str, phrase: str) -> bool:
        """Match full command phrases without partial word collisions."""
        return re.search(rf"\b{re.escape(phrase)}\b", text) is not None

    def _parse_browser_search(self, normalized: str, original: str) -> VoiceIntent | None:
        """Parse browser search queries matching app, action, and clean query string."""
        if "search" not in normalized:
            return None

        # Extract target application from transcript
        app = self._extract_browser_target(normalized) or "chrome"

        # Deterministically extract and clean user search query
        query = self._sanitize_search_query(original)
        if not query:
            logger.info("Browser search rejected; no valid query phrase found in: %s", original)
            return None

        return VoiceIntent(
            intent=VoiceIntentType.BROWSER_SEARCH,
            text=original,
            confidence=0.95,
            target=app,
            query=query,
            params={"application": app, "query": query},
        )

    def _extract_browser_target(self, normalized: str) -> str | None:
        """Extract target browser or application name from normalized text."""
        if any(term in normalized for term in ("settings", "setting", "windows settings", "system settings")):
            return "settings"
        if any(term in normalized for term in ("edge", "microsoft edge", "ms edge")):
            return "edge"
        if any(term in normalized for term in ("chrome", "google chrome", "chrom")):
            return "chrome"
        if "browser" in normalized:
            return "chrome"
        return None

    @staticmethod
    def _sanitize_search_query(text: str) -> str | None:
        """Deterministically extract user search query phrase without command words."""
        if not text:
            return None

        cleaned = text.strip()

        # Step 1: Strip leading command phrases (case-insensitive)
        leading_pattern = (
            r"^(?:\b(?:open|launch|start|please|can you|could you|hey|iris)\b\s*)?"
            r"(?:\b(?:google chrome|microsoft edge|ms edge|windows settings|system settings|settings|setting|chrome|edge|browser)\b\s*)?"
            r"(?:\b(?:and)\b\s*)?"
            r"(?:\b(?:search for|search|look up|find)\b\s*)?"
            r"(?:\b(?:for|about)\b\s*)?"
        )
        cleaned = re.sub(leading_pattern, "", cleaned, flags=re.IGNORECASE).strip()

        # Step 2: Strip trailing browser target phrases (case-insensitive)
        trailing_pattern = (
            r"\s*(?:\b(?:in|on|using|with|via)\b\s*)?"
            r"(?:\b(?:the)\b\s*)?"
            r"\b(?:google chrome|microsoft edge|ms edge|windows settings|system settings|settings|setting|chrome|edge|browser)\b\s*$"
        )
        cleaned = re.sub(trailing_pattern, "", cleaned, flags=re.IGNORECASE).strip()

        # Step 3: Strip any leftover leading search keywords
        cleaned = re.sub(r"^(?:search for|search|for)\s+", "", cleaned, flags=re.IGNORECASE).strip()

        if not cleaned or cleaned.lower() in {"open", "chrome", "edge", "browser", "settings", "setting", "search", "and"}:
            return None

        return cleaned
