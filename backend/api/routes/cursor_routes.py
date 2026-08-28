"""FastAPI route handlers for OS-level system cursor control."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
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
    new_state = system_cursor.toggle(explicit_state)
    cursor_ctrl = getattr(request.app.state, "cursor_controller", None)
    if cursor_ctrl is not None:
        if new_state:
            cursor_ctrl.enable()
        else:
            cursor_ctrl.disable()
    return system_cursor.get_status()


@router.get("/status", response_model=CursorStatusResponse)
async def get_cursor_status(request: Request) -> dict[str, Any]:
    """Return whether OS cursor control is active and current screen dimensions."""
    status = system_cursor.get_status()
    cursor_ctrl = getattr(request.app.state, "cursor_controller", None)
    if cursor_ctrl is not None:
        status["enabled"] = bool(system_cursor.enabled or cursor_ctrl.get_state().enabled)
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
