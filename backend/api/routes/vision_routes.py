"""FastAPI Router for Vision Intelligence Subsystem."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.perception.vision_engine import VisionEngine

router = APIRouter(prefix="/vision", tags=["vision"])

# Shared VisionEngine singleton instance
_vision_engine = VisionEngine()


class PrivacySettingsRequest(BaseModel):
    paused: bool | None = None


@router.get("/context")
def get_visual_context():
    """Return the current visual context snapshot."""
    context = _vision_engine.get_current_context()
    return {
        "app_title": context.app_title,
        "visible_text": context.visible_text,
        "element_count": context.element_count,
        "timestamp": context.timestamp,
        "privacy_redacted": context.privacy_redacted,
    }


@router.post("/capture")
def trigger_capture():
    """Trigger an instant screen frame capture and OCR analysis."""
    context = _vision_engine.capture_and_process()
    return {
        "success": True,
        "app_title": context.app_title,
        "element_count": context.element_count,
        "visible_text": context.visible_text[:100],
    }


@router.post("/privacy")
def update_privacy_settings(req: PrivacySettingsRequest):
    """Update vision privacy settings."""
    if req.paused is not None:
        _vision_engine._privacy_filter.set_paused(req.paused)
    return {
        "success": True,
        "paused": _vision_engine._privacy_filter.paused,
    }
