"""AssistantResponseService synthesizing concise two-way responses and driving optional TTS output."""

from __future__ import annotations

from threading import RLock
from typing import Any

from backend.core.events.bus import EventBus
from backend.utils.logger import get_logger
from backend.voice.speech_output import SpeechOutputManager

logger = get_logger(__name__)


class AssistantResponseService:
    """Manages concise conversational response generation, event publishing, and TTS dispatch."""

    def __init__(
        self,
        speech_output_manager: SpeechOutputManager | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._speech_output_manager = speech_output_manager
        self._event_bus = event_bus
        self._last_response: str = ""
        self._lock = RLock()

    @property
    def last_response(self) -> str:
        with self._lock:
            return self._last_response

    def generate_response(self, intent: str, target: str | None = None, success: bool = True, custom_message: str | None = None) -> str:
        """Synthesize concise conversational text for a voice command outcome."""
        if custom_message:
            return custom_message

        from backend.automation.app_resolver import app_resolver
        canonical = app_resolver.get_canonical_name(target or "") if target else None
        display_target = canonical or (target or "").strip().title() or "Application"

        if intent in ("OPEN_APPLICATION", "OPEN_CHROME", "OPEN_NOTEPAD"):
            return f"{display_target} opened." if success else f"Sir, I couldn't find {display_target} on this computer."

        if intent == "CLOSE_APPLICATION" or intent == "CLOSE_WINDOW":
            return f"{display_target} closed." if success else f"Failed to close {display_target}."

        if intent == "BROWSER_SEARCH":
            return f"Searched for {target or 'query'}." if success else "Search failed."

        return "Command completed." if success else "Command failed."

    def respond(self, text: str, speak: bool = True) -> str:
        """Record response turn, publish event, and speak through TTS if available."""
        with self._lock:
            self._last_response = text
            logger.info("ASSISTANT_RESPONSE: '%s' (speak=%s)", text, speak)

            if self._speech_output_manager and speak:
                try:
                    self._speech_output_manager.speak(text)
                except Exception as err:
                    logger.warning("TTS output failed (non-fatal): %s", err)

            return text
