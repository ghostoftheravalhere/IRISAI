"""Habit Persistence & Memory Integration Store."""

from __future__ import annotations

from threading import RLock

from backend.learning.learning_models import DetectedRoutine, UserPreferences
from backend.memory.memory_manager import MemoryManager
from backend.memory.memory_models import MemoryLayer
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class HabitStore:
    """Interfacing store managing persistence of learned habits and preferences in MemoryManager."""

    def __init__(self, memory_manager: MemoryManager | None = None) -> None:
        self._memory_manager = memory_manager or MemoryManager()
        self._preferences = UserPreferences()
        self._routines: list[DetectedRoutine] = []
        self._lock = RLock()

    @property
    def preferences(self) -> UserPreferences:
        return self._preferences

    def save_preferences(self, prefs: UserPreferences) -> None:
        with self._lock:
            self._preferences = prefs
            self._memory_manager.remember(
                content=f"User preferred browser is {prefs.preferred_browser}, IDE is {prefs.preferred_ide}",
                layer=MemoryLayer.PREFERENCE,
                tags=["preference", "habit"],
            )

    def save_routines(self, routines: list[DetectedRoutine]) -> None:
        with self._lock:
            self._routines = list(routines)
            for r in routines:
                self._memory_manager.remember(
                    content=f"User routine '{r.name}' at {r.trigger_time} apps={r.sequence_apps}",
                    layer=MemoryLayer.SEMANTIC,
                    tags=["routine", "habit"],
                )

    def get_routines(self) -> list[DetectedRoutine]:
        with self._lock:
            return list(self._routines)
