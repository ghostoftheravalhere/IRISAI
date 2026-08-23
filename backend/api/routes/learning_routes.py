"""FastAPI Router for Adaptive Learning & Personalization Engine."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.learning.adaptive_policy import AdaptivePolicy
from backend.learning.behavior_profiler import BehaviorProfiler
from backend.learning.habit_store import HabitStore
from backend.learning.preference_learner import PreferenceLearner
from backend.learning.routine_detector import RoutineDetector
from backend.learning.suggestion_engine import SuggestionEngine

router = APIRouter(prefix="/learning", tags=["learning"])

# Shared singleton instances
_profiler = BehaviorProfiler()
_detector = RoutineDetector()
_learner = PreferenceLearner()
_habit_store = HabitStore()
_engine = SuggestionEngine(habit_store=_habit_store)
_policy = AdaptivePolicy(habit_store=_habit_store)


class PolicyRequest(BaseModel):
    learning_enabled: bool | None = None
    suggestion_frequency: str | None = None


@router.get("/dashboard")
def get_learning_dashboard():
    """Get learning dashboard metrics, preferences, and detected routines."""
    prefs = _habit_store.preferences
    routines = _detector.detect_routines(_profiler)
    freqs = _profiler.get_signal_frequencies()

    return {
        "learning_enabled": prefs.learning_enabled,
        "suggestion_frequency": prefs.suggestion_frequency,
        "preferred_browser": prefs.preferred_browser,
        "preferred_ide": prefs.preferred_ide,
        "signal_count": len(_profiler.get_signals()),
        "signal_frequencies": freqs,
        "routines_count": len(routines),
        "routines": [r.name for r in routines],
    }


@router.get("/suggestions")
def get_active_suggestions():
    """Get active proactive suggestions."""
    suggestions = _engine.generate_suggestions()
    return {
        "count": len(suggestions),
        "suggestions": [
            {
                "id": s.suggestion_id,
                "prompt": s.prompt_text,
                "action": s.suggested_action,
                "confidence": s.confidence,
                "dismissed": s.dismissed,
            }
            for s in suggestions
        ],
    }


@router.post("/suggestions/{suggestion_id}/dismiss")
def dismiss_suggestion(suggestion_id: str):
    """Dismiss a proactive suggestion."""
    dismissed = _engine.dismiss_suggestion(suggestion_id)
    return {"success": True, "dismissed": dismissed}


@router.post("/policy")
def update_policy(req: PolicyRequest):
    """Update learning policy settings."""
    prefs = _policy.update_policy(
        learning_enabled=req.learning_enabled,
        suggestion_frequency=req.suggestion_frequency,
    )
    return {"success": True, "learning_enabled": prefs.learning_enabled}


@router.post("/reset")
def reset_learned_behavior():
    """1-Click reset of learned behavioral habits."""
    reset = _policy.reset_learned_behavior()
    return {"success": True, "reset": reset}
