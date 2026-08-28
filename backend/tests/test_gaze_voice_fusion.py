"""Unit tests for Multimodal Gaze-Voice Fusion Engine."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from backend.fusion.fusion_engine import (
    FusionActionResponse,
    GazeAnchor,
    GazeVoiceFusionEngine,
)
from backend.services.system_cursor import SystemCursor, system_cursor


@pytest.fixture
def mock_cursor_controller():
    mock_ctrl = MagicMock()
    mock_ctrl.get_current_position.return_value = (500, 300)
    return mock_ctrl


@pytest.fixture
def mock_system_cursor():
    mock_sc = MagicMock(spec=SystemCursor)
    mock_sc.enabled = True
    mock_sc.get_cursor_position.return_value = (800, 600)
    mock_sc.click.return_value = True
    mock_sc.double_click.return_value = True
    mock_sc.mouse_down.return_value = True
    mock_sc.mouse_up.return_value = True
    return mock_sc


def test_gaze_anchor_validity():
    """Verify GazeAnchor validity within and outside maximum drift window."""
    now = 1000.0
    anchor = GazeAnchor(x=200, y=150, timestamp=now)

    assert anchor.is_valid(max_drift_seconds=2.0, now=now + 0.5) is True
    assert anchor.is_valid(max_drift_seconds=2.0, now=now + 1.9) is True
    assert anchor.is_valid(max_drift_seconds=2.0, now=now + 2.1) is False
    assert anchor.is_valid(max_drift_seconds=2.0, now=now + 5.0) is False


def test_anchor_gaze_from_cursor_controller(mock_cursor_controller, mock_system_cursor):
    """When speech starts, anchor_gaze captures position from cursor_controller."""
    engine = GazeVoiceFusionEngine(
        cursor_controller=mock_cursor_controller,
        system_cursor_service=mock_system_cursor,
        max_drift_seconds=2.0,
    )

    anchor = engine.handle_speech_start()
    assert anchor.x == 500
    assert anchor.y == 300
    assert engine.get_latest_anchor() == anchor


def test_anchor_gaze_fallback_to_system_cursor(mock_system_cursor):
    """When cursor_controller is absent, anchor_gaze falls back to system_cursor."""
    engine = GazeVoiceFusionEngine(
        cursor_controller=None,
        system_cursor_service=mock_system_cursor,
        max_drift_seconds=2.0,
    )

    anchor = engine.anchor_gaze()
    assert anchor.x == 800
    assert anchor.y == 600


def test_intent_mapping_click_action(mock_cursor_controller, mock_system_cursor):
    """Spoken 'click' command executes Win32 left-click at anchored coordinates."""
    engine = GazeVoiceFusionEngine(
        cursor_controller=mock_cursor_controller,
        system_cursor_service=mock_system_cursor,
        max_drift_seconds=2.0,
    )

    t0 = 100.0
    engine.anchor_gaze(x=640, y=480, timestamp=t0)

    with patch("backend.eye_tracking.click_feedback_overlay.show_click_feedback_popup"):
        resp = engine.process_voice_command("click", timestamp=t0 + 0.4)

    assert resp is not None
    assert resp.success is True
    assert resp.action == "LEFT_CLICK"
    assert resp.target_x == 640
    assert resp.target_y == 480
    assert resp.used_anchor is True
    mock_system_cursor.click.assert_called_once_with(640, 480, button="left")


def test_intent_mapping_double_click_action(mock_cursor_controller, mock_system_cursor):
    """Spoken 'double click' or 'open' executes double click at anchored coordinates."""
    engine = GazeVoiceFusionEngine(
        cursor_controller=mock_cursor_controller,
        system_cursor_service=mock_system_cursor,
        max_drift_seconds=2.0,
    )

    t0 = 100.0
    engine.anchor_gaze(x=320, y=240, timestamp=t0)

    with patch("backend.eye_tracking.click_feedback_overlay.show_click_feedback_popup"):
        resp = engine.process_voice_command("double click", timestamp=t0 + 0.3)

    assert resp is not None
    assert resp.success is True
    assert resp.action == "DOUBLE_CLICK"
    assert resp.target_x == 320
    assert resp.target_y == 240
    assert resp.used_anchor is True
    mock_system_cursor.double_click.assert_called_once_with(320, 240, button="left")


def test_intent_mapping_right_click_action(mock_cursor_controller, mock_system_cursor):
    """Spoken 'right click' or 'menu' executes right click at anchored coordinates."""
    engine = GazeVoiceFusionEngine(
        cursor_controller=mock_cursor_controller,
        system_cursor_service=mock_system_cursor,
        max_drift_seconds=2.0,
    )

    t0 = 100.0
    engine.anchor_gaze(x=400, y=400, timestamp=t0)

    with patch("backend.eye_tracking.click_feedback_overlay.show_click_feedback_popup"):
        resp = engine.process_voice_command("right click", timestamp=t0 + 0.5)

    assert resp is not None
    assert resp.success is True
    assert resp.action == "RIGHT_CLICK"
    assert resp.target_x == 400
    assert resp.target_y == 400
    assert resp.used_anchor is True
    mock_system_cursor.click.assert_called_once_with(400, 400, button="right")


def test_intent_mapping_drag_and_drop_actions(mock_cursor_controller, mock_system_cursor):
    """Spoken 'drag' triggers mouse_down and 'drop' triggers mouse_up."""
    engine = GazeVoiceFusionEngine(
        cursor_controller=mock_cursor_controller,
        system_cursor_service=mock_system_cursor,
        max_drift_seconds=2.0,
    )

    t0 = 100.0
    engine.anchor_gaze(x=100, y=100, timestamp=t0)

    with patch("backend.eye_tracking.click_feedback_overlay.show_click_feedback_popup"):
        resp_drag = engine.process_voice_command("drag this", timestamp=t0 + 0.2)
        assert resp_drag.action == "MOUSE_DOWN"
        assert resp_drag.target_x == 100
        assert resp_drag.target_y == 100
        mock_system_cursor.mouse_down.assert_called_once_with(100, 100, button="left")

        # Now drop at a new location
        engine.anchor_gaze(x=700, y=700, timestamp=t0 + 1.0)
        resp_drop = engine.process_voice_command("drop", timestamp=t0 + 1.2)
        assert resp_drop.action == "MOUSE_UP"
        assert resp_drop.target_x == 700
        assert resp_drop.target_y == 700
        mock_system_cursor.mouse_up.assert_called_once_with(700, 700, button="left")


def test_stale_anchor_fallback_to_live_coordinates(mock_cursor_controller, mock_system_cursor):
    """When anchor is older than max_drift_seconds (2.0s), engine falls back to live cursor."""
    engine = GazeVoiceFusionEngine(
        cursor_controller=mock_cursor_controller,
        system_cursor_service=mock_system_cursor,
        max_drift_seconds=2.0,
    )

    t0 = 100.0
    engine.anchor_gaze(x=100, y=100, timestamp=t0)

    # Change current cursor position to (500, 300)
    mock_cursor_controller.get_current_position.return_value = (500, 300)

    # Execute 3 seconds later (> 2.0s drift)
    with patch("backend.eye_tracking.click_feedback_overlay.show_click_feedback_popup"):
        resp = engine.process_voice_command("click", timestamp=t0 + 3.0)

    assert resp is not None
    assert resp.target_x == 500
    assert resp.target_y == 300
    assert resp.used_anchor is False
    mock_system_cursor.click.assert_called_once_with(500, 300, button="left")


def test_listener_callback_dispatch(mock_cursor_controller, mock_system_cursor):
    """Action listeners receive notifications when actions are executed."""
    engine = GazeVoiceFusionEngine(
        cursor_controller=mock_cursor_controller,
        system_cursor_service=mock_system_cursor,
        max_drift_seconds=2.0,
    )

    received = []
    listener = lambda resp: received.append(resp)
    engine.add_listener(listener)

    with patch("backend.eye_tracking.click_feedback_overlay.show_click_feedback_popup"):
        engine.execute_action("LEFT_CLICK")

    assert len(received) == 1
    assert received[0].action == "LEFT_CLICK"

    # Remove listener and verify no more events
    engine.remove_listener(listener)
    with patch("backend.eye_tracking.click_feedback_overlay.show_click_feedback_popup"):
        engine.execute_action("RIGHT_CLICK")

    assert len(received) == 1


@pytest.mark.parametrize(
    "phrase,expected_action",
    [
        ("Right click", "RIGHT_CLICK"),
        ("RIGHT CLICK", "RIGHT_CLICK"),
        ("Right-Click", "RIGHT_CLICK"),
        ("RightClick", "RIGHT_CLICK"),
        ("do a right click", "RIGHT_CLICK"),
        ("CLICK", "LEFT_CLICK"),
        ("Click", "LEFT_CLICK"),
        ("Left Click", "LEFT_CLICK"),
        ("Double click", "DOUBLE_CLICK"),
        ("DOUBLE CLICK", "DOUBLE_CLICK"),
        ("Double-Click", "DOUBLE_CLICK"),
        ("Drag", "MOUSE_DOWN"),
        ("Drop", "MOUSE_UP"),
    ],
)
def test_case_insensitive_voice_command_mapping(phrase, expected_action, mock_cursor_controller, mock_system_cursor):
    """Verify voice command intent parsing is strictly case-insensitive."""
    engine = GazeVoiceFusionEngine(
        cursor_controller=mock_cursor_controller,
        system_cursor_service=mock_system_cursor,
    )
    with patch("backend.eye_tracking.click_feedback_overlay.show_click_feedback_popup"):
        resp = engine.process_voice_command(phrase)

    assert resp is not None, f"Failed to match phrase: {phrase}"
    assert resp.action == expected_action
    assert resp.success is True
