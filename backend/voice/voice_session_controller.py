"""Voice Session State Machine Controller."""

from __future__ import annotations

from enum import Enum
from threading import RLock

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class VoiceSessionState(str, Enum):
    """Lifecycle states for Voice Session Controller."""

    SLEEPING = "SLEEPING"
    WAKE_DETECTED = "WAKE_DETECTED"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"
    IDLE = "IDLE"


class VoiceSessionController:
    """Manages formal voice session states and transitions."""

    def __init__(self) -> None:
        self._state = VoiceSessionState.SLEEPING
        self._lock = RLock()

    @property
    def state(self) -> VoiceSessionState:
        return self._state

    def set_state(self, new_state: VoiceSessionState) -> None:
        with self._lock:
            logger.info("VoiceSessionController transition: %s -> %s", self._state.value, new_state.value)
            self._state = new_state
