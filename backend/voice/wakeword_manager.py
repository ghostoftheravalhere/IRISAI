"""Wake Word Settings & Lifecycle Manager."""

from __future__ import annotations

from threading import RLock

from backend.utils.logger import get_logger
from backend.voice.wakeword_engine import WakeWordEngine

logger = get_logger(__name__)


class WakeWordManager:
    """Manages wake word configuration, sensitivity, and auto-timeout settings."""

    def __init__(self, engine: WakeWordEngine | None = None) -> None:
        self._engine = engine or WakeWordEngine()
        self._auto_timeout_sec = 5.0
        self._lock = RLock()

    @property
    def engine(self) -> WakeWordEngine:
        return self._engine

    @property
    def auto_timeout_sec(self) -> float:
        return self._auto_timeout_sec

    def update_settings(self, enabled: bool | None = None, sensitivity: float | None = None, timeout_sec: float | None = None) -> dict:
        """Update wake word settings."""
        with self._lock:
            if sensitivity is not None:
                self._engine.set_sensitivity(sensitivity)
            if timeout_sec is not None:
                self._auto_timeout_sec = max(1.0, min(30.0, timeout_sec))

            return {
                "enabled": self._engine.enabled,
                "sensitivity": self._engine.sensitivity,
                "auto_timeout_sec": self._auto_timeout_sec,
            }
