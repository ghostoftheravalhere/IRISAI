"""FastAPI route handlers for OS-level system cursor control."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
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
async def toggle_cursor(body: CursorToggleRequest | None = None) -> dict[str, Any]:
    """Enable/disable OS-level cursor takeover."""
    explicit_state = body.enabled if body else None
    system_cursor.toggle(explicit_state)
    return system_cursor.get_status()


@router.get("/status", response_model=CursorStatusResponse)
async def get_cursor_status() -> dict[str, Any]:
    """Return whether OS cursor control is active and current screen dimensions."""
    return system_cursor.get_status()


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
