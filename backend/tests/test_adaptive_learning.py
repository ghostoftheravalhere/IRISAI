"""Unit tests for Adaptive Learning & Personalization Engine."""

from __future__ import annotations

from backend.learning.adaptive_policy import AdaptivePolicy
from backend.learning.behavior_profiler import BehaviorProfiler
from backend.learning.habit_store import HabitStore
from backend.learning.learning_models import UserPreferences
from backend.learning.preference_learner import PreferenceLearner
from backend.learning.routine_detector import RoutineDetector
from backend.learning.suggestion_engine import SuggestionEngine


def test_behavior_profiler_and_signal_collection():
    profiler = BehaviorProfiler()
    profiler.record_signal("app_launch", "chrome")
    profiler.record_signal("app_launch", "vscode")
    profiler.record_signal("app_launch", "vscode")

    signals = profiler.get_signals()
    freqs = profiler.get_signal_frequencies()

    assert len(signals) == 3
    assert freqs["vscode"] == 2
    assert freqs["chrome"] == 1


def test_routine_detector_and_preference_learner():
    profiler = BehaviorProfiler()
    profiler.record_signal("app_launch", "vscode")
    profiler.record_signal("test_run", "pytest")

    detector = RoutineDetector()
    routines = detector.detect_routines(profiler)
    assert len(routines) == 1
    assert "Evening Developer Routine" in routines[0].name

    learner = PreferenceLearner()
    cur = UserPreferences(preferred_browser="edge")
    updated = learner.update_preferences(profiler, cur)
    assert updated.preferred_browser == "edge"  # Unchanged if chrome frequency == edge


def test_habit_store_and_suggestion_engine():
    store = HabitStore()
    engine = SuggestionEngine(habit_store=store)

    suggestions = engine.generate_suggestions()
    assert len(suggestions) >= 1
    assert suggestions[0].dismissed is False

    dismissed = engine.dismiss_suggestion(suggestions[0].suggestion_id)
    assert dismissed is True


def test_adaptive_policy_and_reset():
    store = HabitStore()
    policy = AdaptivePolicy(habit_store=store)

    updated = policy.update_policy(learning_enabled=False)
    assert updated.learning_enabled is False

    reset = policy.reset_learned_behavior()
    assert reset is True
