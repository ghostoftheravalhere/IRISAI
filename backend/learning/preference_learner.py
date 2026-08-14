"""Statistical Preference Learner Service."""

from __future__ import annotations

from backend.learning.behavior_profiler import BehaviorProfiler
from backend.learning.learning_models import UserPreferences
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class PreferenceLearner:
    """Learns statistical user preferences from interaction frequencies."""

    def update_preferences(self, profiler: BehaviorProfiler, current: UserPreferences) -> UserPreferences:
        """Update UserPreferences based on interaction frequencies."""
        freqs = profiler.get_signal_frequencies()

        pref_browser = current.preferred_browser
        pref_ide = current.preferred_ide
        pref_music = current.preferred_music_app

        if freqs.get("chrome", 0) > freqs.get("edge", 0):
            pref_browser = "chrome"
        elif freqs.get("edge", 0) > freqs.get("chrome", 0):
            pref_browser = "edge"

        return UserPreferences(
            preferred_browser=pref_browser,
            preferred_ide=pref_ide,
            preferred_music_app=pref_music,
            response_length=current.response_length,
            learning_enabled=current.learning_enabled,
            suggestion_frequency=current.suggestion_frequency,
        )
