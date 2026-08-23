"""Proactive Advisory Suggestion Engine Service."""

from __future__ import annotations

from threading import RLock

from backend.learning.habit_store import HabitStore
from backend.learning.learning_models import ProactiveSuggestion
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class SuggestionEngine:
    """Generates non-intrusive, dismissible proactive suggestions. Never executes automatically."""

    def __init__(self, habit_store: HabitStore | None = None) -> None:
        self._habit_store = habit_store or HabitStore()
        self._suggestions: list[ProactiveSuggestion] = []
        self._lock = RLock()

    def generate_suggestions(self) -> list[ProactiveSuggestion]:
        """Generate dismissible suggestions based on routines and preferences."""
        with self._lock:
            self._suggestions.clear()
            routines = self._habit_store.get_routines()

            for r in routines:
                s = ProactiveSuggestion(
                    prompt_text=f"You usually start '{r.name}' around {r.trigger_time}. Would you like to run it now?",
                    suggested_action=f"EXECUTE_ROUTINE_{r.name}",
                    confidence=r.confidence,
                )
                self._suggestions.append(s)

            # Default fallback suggestion
            if not self._suggestions:
                s = ProactiveSuggestion(
                    prompt_text="You usually run backend tests after editing code. Would you like me to run pytest?",
                    suggested_action="RUN_TESTS",
                    confidence=0.85,
                )
                self._suggestions.append(s)

            return list(self._suggestions)

    def dismiss_suggestion(self, suggestion_id: str) -> bool:
        """Dismiss a proactive suggestion."""
        with self._lock:
            for s in self._suggestions:
                if s.suggestion_id == suggestion_id:
                    s.dismissed = True
                    return True
            return False
