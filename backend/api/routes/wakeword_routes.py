"""FastAPI Router for Wake Word & Natural Voice Experience."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.voice.speech_output import SpeechOutputManager
from backend.voice.wakeword_manager import WakeWordManager

router = APIRouter(prefix="/wakeword", tags=["wakeword"])

# Shared WakeWordManager and SpeechOutputManager singleton instances
_wakeword_manager = WakeWordManager()
_speech_output = SpeechOutputManager()


class SettingsRequest(BaseModel):
    enabled: bool | None = None
    sensitivity: float | None = None
    auto_timeout_sec: float | None = None


@router.get("/settings")
def get_wakeword_settings():
    """Get current wake word settings."""
    return {
        "enabled": _wakeword_manager.engine.enabled,
        "sensitivity": _wakeword_manager.engine.sensitivity,
        "auto_timeout_sec": _wakeword_manager.auto_timeout_sec,
    }


@router.post("/settings")
def update_wakeword_settings(req: SettingsRequest):
    """Update wake word sensitivity, enable state, and auto-timeout."""
    res = _wakeword_manager.update_settings(
        enabled=req.enabled,
        sensitivity=req.sensitivity,
        timeout_sec=req.auto_timeout_sec,
    )
    return {"success": True, "settings": res}


@router.post("/stop")
def stop_speech():
    """Instantly interrupt active speech output."""
    stopped = _speech_output.stop(reason="api_request")
    return {"success": True, "stopped": stopped}
