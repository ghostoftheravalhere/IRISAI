"""FastAPI Router for Vision Actions & Desktop Interaction."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.perception.ocr_service import OCREngine
from backend.perception.screen_grounding_engine import ScreenGroundingEngine
from backend.perception.ui_action_resolver import UIActionResolver

router = APIRouter(prefix="/vision/actions", tags=["vision-actions"])

# Shared services
_resolver = UIActionResolver()
_grounding = ScreenGroundingEngine()
_ocr = OCREngine()


class ClickTextRequest(BaseModel):
    text: str


@router.post("/ground")
def ground_phrase(req: ClickTextRequest):
    """Ground a natural language phrase to screen (x, y) coordinates."""
    target_ref = _resolver.resolve_target(req.text)
    ocr_res = _ocr.process_image(None)
    pt = _grounding.ground_target(ocr_res, target_ref)

    if not pt:
        return {"success": False, "message": f"Target '{req.text}' not found."}

    return {
        "success": True,
        "x": pt.x,
        "y": pt.y,
        "confidence": pt.confidence,
        "text_label": pt.text_label,
    }


@router.post("/click-text")
def click_text(req: ClickTextRequest):
    """Ground and simulate visual click at target text."""
    target_ref = _resolver.resolve_target(req.text)
    ocr_res = _ocr.process_image(None)
    pt = _grounding.ground_target(ocr_res, target_ref)

    if not pt:
        return {"success": False, "message": f"Target '{req.text}' not found."}

    return {
        "success": True,
        "action": "CLICK_AT",
        "x": pt.x,
        "y": pt.y,
        "text_label": pt.text_label,
    }
