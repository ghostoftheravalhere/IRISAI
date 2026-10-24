"""FastAPI route handlers for OS-level system cursor control."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.services.system_cursor import system_cursor

router = APIRouter(tags=["cursor"])


class CursorToggleRequest(BaseModel):
    """Request schema for toggling cursor takeover."""

    enabled: bool | None = Field(
        default=None,
        description="Explicit state to set. If None, inverts current state.",
    )


class CursorStatusResponse(BaseModel):
    """Response schema for cursor status."""

    active: bool
    enabled: bool
    dpi_aware: bool
    screen_width: int
    screen_height: int


class CursorMoveRequest(BaseModel):
    """Request schema for direct cursor movement."""

    x: float
    y: float


class CursorClickRequest(BaseModel):
    """Request schema for native click."""

    x: float | None = None
    y: float | None = None
    button: str = "left"


@router.post("/toggle", response_model=CursorStatusResponse)
async def toggle_cursor(request: Request, body: CursorToggleRequest | None = None) -> dict[str, Any]:
    """Enable/disable OS-level cursor takeover."""
    explicit_state = body.enabled if body else None
    target_state = not system_cursor.enabled if explicit_state is None else bool(explicit_state)

    calib_svc = getattr(request.app.state, "eye_calibration", None)
    if target_state and calib_svc is not None and not getattr(calib_svc, "is_calibrated", False):
        raise HTTPException(
            status_code=409,
            detail="Calibration is not authorized. Recalibrate, then try enabling cursor again.",
        )

    new_state = system_cursor.toggle(explicit_state)
    cursor_ctrl = getattr(request.app.state, "cursor_controller", None)
    if cursor_ctrl is not None:
        if new_state:
            cursor_ctrl.enable()
        else:
            cursor_ctrl.disable()
    status = system_cursor.get_status()
    return status


@router.get("/status", response_model=CursorStatusResponse)
async def get_cursor_status(request: Request) -> dict[str, Any]:
    """Return whether OS cursor control is active and current screen dimensions."""
    status = system_cursor.get_status()
    cursor_ctrl = getattr(request.app.state, "cursor_controller", None)
    if cursor_ctrl is not None:
        ctrl_state = cursor_ctrl.get_state()
        status["enabled"] = bool(system_cursor.enabled or ctrl_state.enabled)
        status["active"] = status["enabled"]
    return status


@router.post("/move")
async def move_cursor(body: CursorMoveRequest) -> dict[str, Any]:
    """Move OS cursor to specified coordinate if cursor control is enabled."""
    success = system_cursor.move_cursor(body.x, body.y)
    clamped_x, clamped_y = system_cursor.clamp_coordinates(body.x, body.y)
    return {
        "success": success,
        "x": clamped_x,
        "y": clamped_y,
        "enabled": system_cursor.enabled,
    }


@router.post("/click")
async def click_cursor(body: CursorClickRequest) -> dict[str, Any]:
    """Execute native mouse click if cursor control is enabled."""
    success = system_cursor.click(x=body.x, y=body.y, button=body.button)
    return {
        "success": success,
        "button": body.button,
        "enabled": system_cursor.enabled,
    }


class CursorRecalibrateRequest(BaseModel):
    """Optional payload for cursor recalibration."""

    neutral_x: float | None = None
    neutral_y: float | None = None


@router.post("/recalibrate")
async def recalibrate_cursor(request: Request, body: CursorRecalibrateRequest | None = None) -> dict[str, Any]:
    """Recalibrate gaze neutral center and resting baseline for cursor controller."""
    nx = body.neutral_x if body else None
    ny = body.neutral_y if body else None

    cursor_ctrl = getattr(request.app.state, "cursor_controller", None)
    gaze_srv = getattr(request.app.state, "gaze_service", None)
    if cursor_ctrl is not None and gaze_srv is None:
        gaze_srv = getattr(cursor_ctrl, "_gaze_service", None)

    cal_x, cal_y = 0.50, 0.58
    if cursor_ctrl is not None:
        cal_x, cal_y = cursor_ctrl.recalibrate_center(nx, ny)
    elif gaze_srv is not None and hasattr(gaze_srv, "recalibrate_center"):
        cal_x, cal_y = gaze_srv.recalibrate_center(nx, ny)

    return {
        "status": "recalibrated",
        "neutral_x": round(cal_x, 4),
        "neutral_y": round(cal_y, 4),
    }

