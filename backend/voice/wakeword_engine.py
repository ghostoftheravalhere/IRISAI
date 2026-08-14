"""Continuous Low-Power Wake Word Engine."""

from __future__ import annotations

from threading import RLock
from typing import Any

from backend.core.events.bus import EventBus
from backend.utils.logger import get_logger
from backend.voice.wakeword_events import WakeWordDetectedEvent
from backend.voice.wakeword_provider import MockWakeWordProvider, WakeWordProvider

logger = get_logger(__name__)


class WakeWordEngine:
    """Low-power continuous audio frame monitoring engine (<2% idle CPU)."""

    def __init__(
        self,
        provider: WakeWordProvider | None = None,
        event_bus: EventBus | None = None,
        sensitivity: float = 0.5,
        enabled: bool = True,
    ) -> None:
        self._provider = provider or MockWakeWordProvider()
        self._event_bus = event_bus
        self._sensitivity = sensitivity
        self._enabled = enabled
        self._lock = RLock()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def sensitivity(self) -> float:
        return self._sensitivity

    def set_sensitivity(self, sensitivity: float) -> None:
        with self._lock:
            self._sensitivity = max(0.1, min(0.9, sensitivity))

    def process_frame(self, audio_frame: Any) -> tuple[bool, str, float]:
        """Process an audio frame and emit WakeWordDetectedEvent if triggered."""
        with self._lock:
            if not self._enabled:
                return False, "", 0.0

            detected, keyword, confidence = self._provider.detect(audio_frame, self._sensitivity)
            if detected:
                logger.info("WakeWordEngine detected '%s' (conf=%.2f)", keyword, confidence)
                if self._event_bus:
                    self._event_bus.publish(
                        WakeWordDetectedEvent(keyword=keyword, confidence=confidence)
                    )
                return True, keyword, confidence

            return False, "", 0.0
