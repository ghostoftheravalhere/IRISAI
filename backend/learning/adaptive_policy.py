"""Adaptive Privacy Policy & User Preference Manager."""

from __future__ import annotations

from threading import RLock

from backend.learning.habit_store import HabitStore
from backend.learning.learning_models import UserPreferences
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class AdaptivePolicy:
    """Manages learning privacy policy, ON/OFF state, and 1-click memory reset."""

    def __init__(self, habit_store: HabitStore | None = None) -> None:
        self._habit_store = habit_store or HabitStore()
        self._lock = RLock()

    def update_policy(self, learning_enabled: bool | None = None, suggestion_frequency: str | None = None) -> UserPreferences:
        """Update user learning policy settings."""
        with self._lock:
            cur = self._habit_store.preferences
            new_prefs = UserPreferences(
                preferred_browser=cur.preferred_browser,
                preferred_ide=cur.preferred_ide,
                preferred_music_app=cur.preferred_music_app,
                response_length=cur.response_length,
                learning_enabled=learning_enabled if learning_enabled is not None else cur.learning_enabled,
                suggestion_frequency=suggestion_frequency if suggestion_frequency is not None else cur.suggestion_frequency,
            )
            self._habit_store.save_preferences(new_prefs)
            logger.info("Updated AdaptivePolicy: learning_enabled=%s", new_prefs.learning_enabled)
            return new_prefs

    def reset_learned_behavior(self) -> bool:
        """1-Click reset of all learned behavioral habits and preferences."""
        with self._lock:
            self._habit_store.save_preferences(UserPreferences())
            self._habit_store.save_routines([])
            logger.info("Reset all learned behavioral habits.")
            return True
