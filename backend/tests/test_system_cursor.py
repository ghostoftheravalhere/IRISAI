"""Unit tests for Native Win32 OS-Level Cursor Control Engine."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.services.system_cursor import (
    SystemCursor,
    get_screen_dimensions,
    set_dpi_awareness,
    system_cursor,
)


@pytest.fixture(autouse=True)
def reset_cursor_state():
    """Ensure system_cursor singleton starts disabled for every test."""
    system_cursor.enabled = False
    yield
    system_cursor.enabled = False


def test_dpi_awareness_call():
    """Verify set_dpi_awareness executes gracefully."""
    result = set_dpi_awareness()
    assert isinstance(result, bool)


def test_screen_dimensions():
    """Verify screen dimensions return positive integers."""
    width, height = get_screen_dimensions()
    assert isinstance(width, int) and width > 0
    assert isinstance(height, int) and height > 0


def test_coordinate_clamping():
    """Verify coordinate clamping strictly enforces screen boundaries."""
    cursor = SystemCursor(enabled=False)
    width, height = cursor.screen_size

    # Valid coordinates within screen
    cx, cy = cursor.clamp_coordinates(100, 150)
    assert cx == 100
    assert cy == 150

    # Negative coordinates clamped to zero
    cx, cy = cursor.clamp_coordinates(-50, -100)
    assert cx == 0
    assert cy == 0

    # Coordinates exceeding screen size clamped to max bounds
    cx, cy = cursor.clamp_coordinates(width + 500, height + 500)
    assert cx == width - 1
    assert cy == height - 1

    # Floating point rounding
    cx, cy = cursor.clamp_coordinates(10.6, 20.4)
    assert cx == 11
    assert cy == 20


def test_toggle_state_transitions():
    """Verify toggle method handles both explicit and implicit transitions."""
    cursor = SystemCursor(enabled=False)
    assert not cursor.enabled

    # Implicit toggle: False -> True
    state = cursor.toggle()
    assert state is True
    assert cursor.enabled is True

    # Implicit toggle: True -> False
    state = cursor.toggle()
    assert state is False
    assert cursor.enabled is False

    # Explicit toggle: set True
    state = cursor.toggle(True)
    assert state is True
    assert cursor.enabled is True

    # Explicit toggle: set False
    state = cursor.toggle(False)
    assert state is False
    assert cursor.enabled is False


def test_cursor_action_when_disabled():
    """Verify move and click return False when cursor takeover is disabled."""
    cursor = SystemCursor(enabled=False)

    assert cursor.move_cursor(100, 100) is False
    assert cursor.click(100, 100, button="left") is False
    assert cursor.click(button="right") is False


def test_cursor_action_when_enabled():
    """Verify move and click execute successfully when enabled."""
    cursor = SystemCursor(enabled=True)

    # In simulated / test mode, move and click should succeed
    assert cursor.move_cursor(100, 100) is True
    assert cursor.click(100, 100, button="left") is True
    assert cursor.click(button="right") is True
    assert cursor.click(button="middle") is True


def test_api_cursor_status_endpoint():
    """Verify GET /api/cursor/status endpoint returns valid status."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/cursor/status")
    assert response.status_code == 200
    data = response.json()
    assert "enabled" in data
    assert "active" in data
    assert "screen_width" in data
    assert "screen_height" in data
    assert data["screen_width"] > 0
    assert data["screen_height"] > 0


def test_api_cursor_toggle_endpoint():
    """Verify POST /api/cursor/toggle endpoint enables and disables cursor takeover."""
    app = create_app()
    client = TestClient(app)

    # Ensure disabled initially
    system_cursor.enabled = False

    # Toggle to True
    res1 = client.post("/api/cursor/toggle", json={"enabled": True})
    assert res1.status_code == 200
    assert res1.json()["enabled"] is True
    assert system_cursor.enabled is True

    # Toggle to False
    res2 = client.post("/api/cursor/toggle", json={"enabled": False})
    assert res2.status_code == 200
    assert res2.json()["enabled"] is False
    assert system_cursor.enabled is False

    # Toggle without explicit body (invert state)
    res3 = client.post("/api/cursor/toggle", json={})
    assert res3.status_code == 200
    assert res3.json()["enabled"] is True
    assert system_cursor.enabled is True


def test_api_cursor_move_and_click_endpoints():
    """Verify POST /api/cursor/move and /api/cursor/click endpoints."""
    app = create_app()
    client = TestClient(app)

    # Disabled
    system_cursor.enabled = False
    move_res = client.post("/api/cursor/move", json={"x": 500, "y": 400})
    assert move_res.status_code == 200
    assert move_res.json()["success"] is False

    # Enabled
    system_cursor.enabled = True
    move_res2 = client.post("/api/cursor/move", json={"x": 500, "y": 400})
    assert move_res2.status_code == 200
    assert move_res2.json()["success"] is True
    assert move_res2.json()["x"] == 500
    assert move_res2.json()["y"] == 400

    click_res = client.post("/api/cursor/click", json={"x": 200, "y": 200, "button": "left"})
    assert click_res.status_code == 200
    assert click_res.json()["success"] is True
    assert click_res.json()["button"] == "left"
