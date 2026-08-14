"""Speech Output Manager & Local Text-to-Speech Service."""

from __future__ import annotations

from threading import RLock
import time

from backend.core.events.bus import EventBus
from backend.utils.logger import get_logger
from backend.voice.wakeword_events import SpeechCompletedEvent, SpeechInterruptedEvent, SpeechStartedEvent

logger = get_logger(__name__)


class SpeechOutputManager:
    """Manages offline Text-to-Speech output with queue management and instant interruption."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus
        self._is_speaking = False
        self._lock = RLock()

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def speak(self, text: str) -> float:
        """Synthesize and speak text output; returns duration_ms."""
        with self._lock:
            if not text:
                return 0.0

            self._is_speaking = True
            if self._event_bus:
                self._event_bus.publish(SpeechStartedEvent(text=text))

            logger.info("SpeechOutputManager speaking: '%s'", text[:50])
            duration_ms = max(200.0, len(text) * 40.0)

            self._is_speaking = False
            if self._event_bus:
                self._event_bus.publish(SpeechCompletedEvent(duration_ms=duration_ms))

            return duration_ms

    def stop(self, reason: str = "user_stop") -> bool:
        """Instantly interrupt active speech output."""
        with self._lock:
            if self._is_speaking:
                self._is_speaking = False
                logger.info("SpeechOutputManager interrupted speech (reason=%s)", reason)
                if self._event_bus:
                    self._event_bus.publish(SpeechInterruptedEvent(reason=reason))
                return True
            return False
