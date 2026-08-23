"""FastAPI Router for Desktop World Model Context State and History."""

from __future__ import annotations

from fastapi import APIRouter

from backend.context.world_model import WorldModel, get_world_model_metrics

router = APIRouter(prefix="/context", tags=["world-model"])

_GLOBAL_WORLD_MODEL = WorldModel()


def get_global_world_model() -> WorldModel:
    return _GLOBAL_WORLD_MODEL


@router.get("/world")
def get_desktop_world_state():
    """Get real-time unified DesktopWorldState and context metrics."""
    wm = get_global_world_model()
    st = wm.current_state
    metrics = get_world_model_metrics()

    return {
        "world_state": {
            "active_application": st.active_application,
            "active_window": st.active_window,
            "visible_documents": st.visible_documents,
            "visible_browser_tabs": st.visible_browser_tabs,
            "selected_text": st.selected_text,
            "clipboard": st.clipboard,
            "focused_control": st.focused_control,
            "visible_dialogs": st.visible_dialogs,
            "notifications": st.notifications,
            "current_task": st.current_task,
            "user_goal": st.user_goal,
            "confidence": st.confidence,
            "current_url": st.current_url,
            "page_title": st.page_title,
            "current_project": st.current_project,
            "current_file": st.current_file,
            "cursor_line": st.cursor_line,
            "is_debugging": st.is_debugging,
            "terminal_active": st.terminal_active,
            "audio_playing": st.audio_playing,
            "system_state": st.system_state,
            "inferred_activity": st.inferred_activity,
            "timestamp": st.timestamp,
        },
        "metrics": metrics,
    }


@router.get("/activity")
def get_inferred_user_activity():
    """Get current inferred user activity classification and confidence."""
    wm = get_global_world_model()
    st = wm.current_state
    return {
        "inferred_activity": st.inferred_activity,
        "active_application": st.active_application,
        "confidence": st.confidence,
        "timestamp": st.timestamp,
    }


@router.get("/history")
def get_desktop_world_history():
    """Get history timeline of past 50 desktop context state changes."""
    wm = get_global_world_model()
    history = wm.get_history()
    return [
        {
            "active_application": st.active_application,
            "active_window": st.active_window,
            "timestamp": st.timestamp,
        }
        for st in history
    ]


@router.get("/snapshot")
def get_world_model_snapshot():
    """Get unified WorldModel snapshot (application, window, target, person)."""
    from backend.brain.world_model import world_model
    return world_model.snapshot().to_dict()
