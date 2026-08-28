"""Unit tests for Pre-Blink Freeze Buffer and EAR Freeze Gate in CursorController."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.eye_tracking.action_engine import ActionState, ActionType
from backend.eye_tracking.blink_detection_service import BlinkState
from backend.eye_tracking.cursor_controller import (
    CursorController,
    CursorControllerConfig,
)
from backend.eye_tracking.gaze_service import EyeGazeService, GazeEstimate
from backend.services.system_cursor import system_cursor


class FakeGazeService:
    def __init__(self, gaze_x: float = 0.5, gaze_y: float = 0.5):
        self.gaze = GazeEstimate(
            eye_center=(0.5, 0.5),
            raw_x=gaze_x,
            raw_y=gaze_y,
            x=gaze_x,
            y=gaze_y,
            confidence=0.9,
            captured_at=100.0,
        )

    def get_latest_gaze(self) -> GazeEstimate | None:
        return self.gaze

    def set_gaze(self, x: float, y: float):
        self.gaze = GazeEstimate(
            eye_center=(x, y),
            raw_x=x,
            raw_y=y,
            x=x,
            y=y,
            confidence=0.9,
            captured_at=100.0,
        )


def _make_blink_state(
    smoothed_ear: float = 0.35,
    hold_active: bool = False,
    left_open: bool = True,
    right_open: bool = True,
) -> BlinkState:
    return BlinkState(
        leftEyeOpen=left_open,
        rightEyeOpen=right_open,
        leftBlink=not left_open,
        rightBlink=not right_open,
        bothBlink=not (left_open or right_open),
        intentionalBlink=hold_active,
        blinkDurationMs=500.0 if hold_active else 0.0,
        holdActive=hold_active,
        holdProgress=1.0 if hold_active else 0.0,
        holdDurationMs=500.0 if hold_active else 0.0,
        leftEar=smoothed_ear,
        rightEar=smoothed_ear,
        smoothedLeftEar=smoothed_ear,
        smoothedRightEar=smoothed_ear,
        smoothedEar=smoothed_ear,
        closedFrames=0 if (left_open and right_open) else 5,
        openFrames=10 if (left_open and right_open) else 0,
        measuredFps=30.0,
        updatedAt=100.0,
    )


def test_history_buffer_rolling_update():
    """Verify history buffer stores up to maxlen coordinates during normal movement."""
    gaze_svc = FakeGazeService(0.5, 0.5)
    config = CursorControllerConfig(
        history_buffer_maxlen=5,
        ear_freeze_threshold=0.28,
    )
    ctrl = CursorController(gaze_service=gaze_svc, config=config)
    ctrl._load_pyautogui = lambda: MagicMock(size=lambda: (1920, 1080), position=lambda: (960, 540), moveTo=lambda *a, **k: None)
    ctrl.enable()

    # Move across 5 frames
    for i in range(5):
        gaze_svc.set_gaze(0.5 + i * 0.02, 0.5 + i * 0.02)
        ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.35))

    assert len(ctrl.history_buffer) == 5
    oldest_x, oldest_y = ctrl.history_buffer[0]
    newest_x, newest_y = ctrl.history_buffer[-1]
    assert oldest_x != newest_x or oldest_y != newest_y


def test_ear_freeze_gate_blocks_movement_during_blink():
    """When EAR falls below threshold, cursor movement should freeze."""
    gaze_svc = FakeGazeService(0.5, 0.5)
    config = CursorControllerConfig(
        history_buffer_maxlen=10,
        ear_freeze_threshold=0.28,
    )
    ctrl = CursorController(gaze_service=gaze_svc, config=config)
    ctrl._load_pyautogui = lambda: MagicMock(size=lambda: (1920, 1080), position=lambda: (960, 540), moveTo=lambda *a, **k: None)
    ctrl.enable()

    # 1. Move to stable position (960, 540)
    ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.35))
    initial_last_x = ctrl._last_x
    initial_last_y = ctrl._last_y

    # 2. Simulate eyelid closing (EAR drops to 0.20 and gaze dips downward to Y=0.85)
    gaze_svc.set_gaze(0.5, 0.85)
    with patch.object(system_cursor, "move_cursor") as mock_move:
        ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.20, hold_active=True))
        # Move cursor should not be called while frozen
        mock_move.assert_not_called()

    # Cursor position should remain at the pre-blink position
    assert ctrl._last_x == initial_last_x
    assert ctrl._last_y == initial_last_y


def test_retro_click_pulls_pre_blink_coordinates():
    """When a blink click triggers, it must use the oldest pre-blink coordinates from history_buffer[0]."""
    gaze_svc = FakeGazeService(0.40, 0.40)
    config = CursorControllerConfig(
        history_buffer_maxlen=10,
        ear_freeze_threshold=0.28,
    )
    ctrl = CursorController(gaze_service=gaze_svc, config=config)
    ctrl._load_pyautogui = lambda: MagicMock(size=lambda: (1920, 1080), position=lambda: (960, 540), moveTo=lambda *a, **k: None)
    ctrl.enable()

    # Step 1: User focuses on a button at (0.40, 0.40) for several frames with open eyes
    for _ in range(5):
        ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.36))

    target_pre_blink_x, target_pre_blink_y = ctrl.history_buffer[0]

    # Step 2: User blinks (EAR drops to 0.18, pupil dips down to 0.80)
    gaze_svc.set_gaze(0.40, 0.80)
    ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.18, hold_active=True))

    # Step 3: Intentional blink fires LEFT_CLICK action
    action = ActionState(
        action=ActionType.LEFT_CLICK,
        timestamp=105.0,
        sourceGesture=None,
        sourceGestureTimestamp=104.5,
        cursorPaused=False,
        dragMode=False,
        cooldownActive=False,
    )

    with patch.object(system_cursor, "click") as mock_click:
        ctrl.update(action_state=action, blink_state=_make_blink_state(smoothed_ear=0.18, hold_active=True))
        mock_click.assert_called_once_with(target_pre_blink_x, target_pre_blink_y, button="left")


def test_freeze_resumes_when_ear_opens():
    """When eyes return to open state, the cursor unfreezes and moves again."""
    gaze_svc = FakeGazeService(0.5, 0.5)
    config = CursorControllerConfig(
        history_buffer_maxlen=10,
        ear_freeze_threshold=0.28,
    )
    ctrl = CursorController(gaze_service=gaze_svc, config=config)
    ctrl._load_pyautogui = lambda: MagicMock(size=lambda: (1920, 1080), position=lambda: (960, 540), moveTo=lambda *a, **k: None)
    ctrl.enable()

    # Fill buffer
    ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.35))

    # Freeze
    ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.15))
    assert ctrl._is_frozen_by_ear is True

    # Unfreeze (EAR > 0.28 and eyes open)
    gaze_svc.set_gaze(0.7, 0.7)
    with patch.object(system_cursor, "move_cursor") as mock_move:
        ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.35, left_open=True, right_open=True))
        assert ctrl._is_frozen_by_ear is False
        mock_move.assert_called_once()
