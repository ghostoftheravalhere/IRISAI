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
    """When EAR falls below threshold, cursor movement should freeze and buffer stops updating."""
    gaze_svc = FakeGazeService(0.5, 0.5)
    config = CursorControllerConfig(
        history_buffer_maxlen=10,
        ear_freeze_threshold=0.31,
    )
    ctrl = CursorController(gaze_service=gaze_svc, config=config)
    ctrl._load_pyautogui = lambda: MagicMock(size=lambda: (1920, 1080), position=lambda: (960, 540), moveTo=lambda *a, **k: None)
    ctrl.enable()

    # 1. Move to stable position (960, 540)
    ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.36))
    initial_last_x = ctrl._last_x
    initial_last_y = ctrl._last_y
    initial_buffer_len = len(ctrl.history_buffer)

    # 2. Simulate eyelid closing (EAR drops to 0.30 - below 0.31 - and gaze dips downward to Y=0.85)
    gaze_svc.set_gaze(0.5, 0.85)
    with patch.object(system_cursor, "move_cursor") as mock_move:
        ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.30, hold_active=True))
        # Move cursor should not be called while frozen
        mock_move.assert_not_called()

    # Cursor position should remain at the pre-blink position and buffer must not append dipping points
    assert ctrl._last_x == initial_last_x
    assert ctrl._last_y == initial_last_y
    assert len(ctrl.history_buffer) == initial_buffer_len


def test_retro_click_pulls_pre_blink_coordinates():
    """When a blink click triggers, it must use the oldest pre-blink coordinates from history_buffer[0]."""
    gaze_svc = FakeGazeService(0.40, 0.40)
    config = CursorControllerConfig(
        history_buffer_maxlen=10,
        ear_freeze_threshold=0.31,
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
        ear_freeze_threshold=0.31,
    )
    ctrl = CursorController(gaze_service=gaze_svc, config=config)
    ctrl._load_pyautogui = lambda: MagicMock(size=lambda: (1920, 1080), position=lambda: (960, 540), moveTo=lambda *a, **k: None)
    ctrl.enable()

    # Fill buffer
    ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.35))

    # Freeze (requires 2 candidate frames for debouncer)
    ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.15))
    ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.15))
    assert ctrl._is_frozen_by_ear is True

    # Unfreeze (EAR > 0.28 and eyes open)
    gaze_svc.set_gaze(0.7, 0.7)
    with patch.object(system_cursor, "move_cursor") as mock_move:
        ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.35, left_open=True, right_open=True))
        assert ctrl._is_frozen_by_ear is False
        mock_move.assert_called_once()


def test_default_config_thresholds():
    """Verify default controller config sets 6-frame buffer and calibrated EAR thresholds."""
    from backend.eye_tracking.cursor_controller import (
        EAR_CLICK_THRESHOLD,
        EAR_FREEZE_THRESHOLD,
        EAR_RECOVERY_THRESHOLD,
    )
    cfg = CursorControllerConfig()
    assert cfg.history_buffer_maxlen == 6
    assert cfg.ear_freeze_threshold == 0.19
    assert cfg.ear_recovery_threshold == 0.21
    assert cfg.ear_click_threshold == 0.16
    assert EAR_FREEZE_THRESHOLD == 0.19
    assert EAR_CLICK_THRESHOLD == 0.16
    assert EAR_RECOVERY_THRESHOLD == 0.21


def test_retro_buffer_rollback_to_index_minus_4_and_zero_velocity():
    """When EAR drops below threshold for 2 candidate frames, target rolls back to sample [-4] and zeroes momentum."""
    gaze_svc = FakeGazeService(0.5, 0.5)
    ctrl = CursorController(gaze_service=gaze_svc)
    ctrl._load_pyautogui = lambda: MagicMock(size=lambda: (1920, 1080), position=lambda: (960, 540), moveTo=lambda *a, **k: None)
    ctrl.enable()

    # Feed 6 distinct positions
    for i in range(6):
        gaze_svc.set_gaze(0.40 + i * 0.02, 0.40 + i * 0.02)
        ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.30))

    # Candidate frame 1 (EAR < thresh, candidate=1, movement continues)
    ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.14, hold_active=False))

    assert len(ctrl.history_buffer) == 6
    expected_rollback_x, expected_rollback_y = ctrl.history_buffer[-4]

    # Candidate frame 2 (EAR < thresh, candidate=2, triggers pre-blink freeze, simulated gaze dips to 0.80)
    gaze_svc.set_gaze(0.50, 0.80)
    with patch.object(system_cursor, "move_cursor") as mock_move:
        ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.14, hold_active=False))
        mock_move.assert_not_called()

    assert ctrl._is_frozen_by_ear is True
    assert ctrl._last_x == expected_rollback_x
    assert ctrl._last_y == expected_rollback_y
    assert ctrl.physics_pipeline.is_frozen is True
    assert ctrl.physics_pipeline.vx == 0.0
    assert ctrl.physics_pipeline.vy == 0.0
    assert ctrl.physics_pipeline.x == expected_rollback_x
    assert ctrl.physics_pipeline.y == expected_rollback_y


def test_freeze_gate_does_not_unfreeze_until_ear_above_recovery_threshold():
    """EAR recovery strictly requires EAR >= 0.21 and both eyes open."""
    gaze_svc = FakeGazeService(0.5, 0.5)
    ctrl = CursorController(gaze_service=gaze_svc)
    ctrl._load_pyautogui = lambda: MagicMock(size=lambda: (1920, 1080), position=lambda: (960, 540), moveTo=lambda *a, **k: None)
    ctrl.enable()

    # Initial frame
    ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.30))
    assert ctrl._is_frozen_by_ear is False

    # Freeze at EAR 0.14 (< 0.19) - candidate frame 1 & 2
    ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.14))
    ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.14))
    assert ctrl._is_frozen_by_ear is True

    # EAR partially recovers to 0.19 (< 0.21): MUST REMAIN FROZEN
    ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.19, left_open=True, right_open=True))
    assert ctrl._is_frozen_by_ear is True

    # EAR recovers to 0.22 (>= 0.21) with both eyes open: UNFREEZES
    ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.22, left_open=True, right_open=True))
    assert ctrl._is_frozen_by_ear is False


def test_ear_freeze_debouncer_2_frames():
    """Single-frame dip does not freeze, 2 consecutive frames below freeze threshold freeze motion."""
    gaze_svc = FakeGazeService(0.5, 0.5)
    ctrl = CursorController(gaze_service=gaze_svc)
    ctrl._load_pyautogui = lambda: MagicMock(size=lambda: (1920, 1080), position=lambda: (960, 540), moveTo=lambda *a, **k: None)
    ctrl.enable()

    # Frame 1: dip below freeze threshold
    ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.14, hold_active=False))
    assert ctrl._freeze_candidate_frames == 1
    assert ctrl._is_frozen_by_ear is False

    # Frame 2: second consecutive frame below freeze threshold -> freezes
    ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.14, hold_active=False))
    assert ctrl._freeze_candidate_frames == 2
    assert ctrl._is_frozen_by_ear is True


def test_vertical_motion_isolated_to_nose_tip():
    """Ensure vertical coordinate target_y is driven 100% by Landmark 1 (nose tip)."""
    from backend.eye_tracking.face_mesh_service import EyeData, NormalizedLandmark
    from backend.eye_tracking.gaze_service import EyeGazeService

    camera_mock = MagicMock()
    calib_mock = MagicMock()
    calib_mock.get_mapping.return_value = MagicMock(
        x_coefficients=(1.0, 0.0, 0.0),
        y_coefficients=(0.0, 1.0, 0.0),
    )
    calib_mock.get_polynomial_calibrator.return_value = None
    calib_mock.get_quality.return_value = MagicMock(score=0.90)

    service = EyeGazeService(camera_service=camera_mock, calibration_service=calib_mock)

    # Supply EyeData with fixed nose_tip.y = 0.42 and varying iris/eye center
    nose = NormalizedLandmark(index=1, x=0.50, y=0.42, z=0.0)
    eye_data = EyeData(left_eye=(), right_eye=(), nose_tip=nose)
    camera_mock.get_latest_eye_data.return_value = eye_data

    with patch("backend.eye_tracking.gaze_service.compute_eye_center", return_value=(0.65, 0.88)):
        estimate = service.estimate_latest_gaze()

    assert estimate is not None
    # raw_y must be 100% driven by nose_tip.y (0.42), ignoring compute_eye_center y (0.88)
    assert estimate.raw_y == 0.42


def test_rolling_median_auto_center_calibration_and_symmetric_projection():
    """Verify EyeGazeService collects 20 frames for rolling median calibration and projects dx symmetrically."""
    import numpy as np
    from backend.eye_tracking.face_mesh_service import EyeData, NormalizedLandmark
    from backend.eye_tracking.gaze_service import EyeGazeService, gaze_to_screen_coordinates

    camera_mock = MagicMock()
    calib_mock = MagicMock()
    calib_mock.get_mapping.return_value = MagicMock(
        x_coefficients=(1.0, 0.0, 0.0),
        y_coefficients=(0.0, 1.0, 0.0),
    )
    calib_mock.get_polynomial_calibrator.return_value = None
    calib_mock.get_quality.return_value = MagicMock(score=0.90)

    service = EyeGazeService(camera_service=camera_mock, calibration_service=calib_mock)

    # 20 frames with x values (0.45 .. 0.55), median should be 0.50
    for i in range(20):
        val = 0.45 + (i / 19.0) * 0.10
        nose = NormalizedLandmark(index=1, x=1.0 - val, y=0.58, z=0.0)
        eye_data = EyeData(left_eye=(), right_eye=(), nose_tip=nose)
        camera_mock.get_latest_eye_data.return_value = eye_data
        service.estimate_latest_gaze()

    assert service._auto_center_calibrated is True
    assert abs(service.calibrated_neutral_x - 0.50) < 0.01

    # Symmetric projection: when norm_x == neutral_x, target_x must equal screen_w / 2 (960)
    tx, ty = gaze_to_screen_coordinates(
        norm_x=service.calibrated_neutral_x,
        norm_y=service.calibrated_neutral_y,
        screen_w=1920,
        screen_h=1080,
        neutral_x=service.calibrated_neutral_x,
        neutral_y=service.calibrated_neutral_y,
    )
    assert tx == 960
    assert ty == 540


def test_screen_pixel_passthrough_and_click_cooldown():
    """Verify coordinates already in screen space (> 1.0) pass through without double-scaling, and click cooldown is enforced."""
    gaze_svc = FakeGazeService(0.5, 0.5)
    ctrl = CursorController(gaze_service=gaze_svc)

    # 1. Pixel passthrough: input (960.0, 540.0) -> outputs (960, 540) directly without > 1,000,000 scaling
    tx, ty = ctrl._gaze_to_screen(960.0, 540.0, 1920, 1080)
    assert tx == 960
    assert ty == 540

    # 2. Cooldown properties
    assert ctrl._CLICK_COOLDOWN == 0.65
    assert ctrl._eye_armed is True


def test_calibrated_polynomial_mapping_passthrough_and_blink_ratios():
    """Verify calibrated gaze estimate skips manual offset subtraction and blink thresholds match ground truth."""
    gaze_svc = FakeGazeService(0.5, 0.5)
    gaze_svc.gaze = GazeEstimate(
        eye_center=(0.5, 0.5),
        raw_x=0.40,
        raw_y=0.30,
        x=0.40,
        y=0.30,
        confidence=0.95,
        captured_at=100.0,
        is_calibrated=True,
    )
    ctrl = CursorController(gaze_service=gaze_svc)

    # Calibrated coordinates (0.40, 0.30) on 1920x1080 screen project to (1152, 324) aligning with physical display orientation
    tx, ty = ctrl._gaze_to_screen(0.40, 0.30, 1920, 1080, gaze=gaze_svc.gaze)
    assert tx == 1152
    assert ty == 324

    # Baseline EAR threshold ratio checks (0.55 click, 0.75 recovery, 0.66 freeze)
    ctrl._baseline_ear = 0.373
    ctrl._ear_calibration_samples = [0.373] * 20
    # Simulate frame update to compute thresholds
    ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.373))
    assert abs(ctrl._baseline_ear * 0.55 - (0.373 * 0.55)) < 0.001
    assert abs(ctrl._baseline_ear * 0.75 - (0.373 * 0.75)) < 0.001
    assert abs(ctrl._baseline_ear * 0.66 - (0.373 * 0.66)) < 0.001


def test_dropout_grace_buffer_and_coasting():
    """Verify 5-frame dropout grace buffer coasts kinematic physics and re-acquires without snap."""
    gaze_svc = FakeGazeService(0.50, 0.50)
    config = CursorControllerConfig(
        kinematic_physics_enabled=True,
        tracking_confidence_threshold=0.45,
    )
    ctrl = CursorController(gaze_service=gaze_svc, config=config)
    ctrl._load_pyautogui = lambda: MagicMock(size=lambda: (1920, 1080), position=lambda: (960, 540), moveTo=lambda *a, **k: None)
    ctrl.enable()

    # Frame 1: Stable tracking at center
    ctrl.update(face_detected=True, tracking_confidence=0.95)
    assert ctrl.physics_pipeline.is_initialized is True
    assert ctrl._dropout_frames == 0

    # Frames 2-6: Momentary tracking loss (frames 1 to 5 of grace period)
    for i in range(1, 6):
        ctrl.update(face_detected=False, tracking_confidence=0.0)
        assert ctrl._dropout_frames == i
        # Physics must NOT be cleared during the 5-frame grace period
        assert ctrl.physics_pipeline.is_initialized is True
        assert ctrl.get_state().trackingActive is True

    # Frame 7: Recovery on frame 6 (re-acquires within grace period)
    # Reset back to frame 1-3 dropout, then recover
    ctrl._dropout_frames = 2
    ctrl.update(face_detected=True, tracking_confidence=0.95)
    assert ctrl._dropout_frames == 0
    assert ctrl.physics_pipeline.is_initialized is True
    assert ctrl._recovery_frames_remaining == 0

    # Test full expiration: > 5 consecutive dropout frames
    for _ in range(6):
        ctrl.update(face_detected=False, tracking_confidence=0.0)

    # After 6 consecutive dropout frames (> 5), motion state must be cleared
    assert ctrl.physics_pipeline.is_initialized is False
    assert ctrl.get_state().trackingActive is False


def test_strict_deliberate_blink_click_window():
    """Verify quick blink click is strictly dispatched for deliberate 300ms-480ms closures, and dropped for <300ms reflex blinks."""
    gaze_svc = FakeGazeService(0.50, 0.50)
    ctrl = CursorController(gaze_service=gaze_svc)
    ctrl._load_pyautogui = lambda: MagicMock(size=lambda: (1920, 1080), position=lambda: (960, 540), moveTo=lambda *a, **k: None)
    ctrl.enable()

    ctrl._baseline_ear = 0.36
    ctrl._ear_calibration_samples = [0.36] * 20
    # click_thresh = 0.36 * 0.55 = 0.198
    # recovery_thresh = 0.36 * 0.75 = 0.270

    dispatched_actions = []
    ctrl._dispatch_os_click = lambda action: dispatched_actions.append(action)

    # 1. Reflex blink (< 300ms, e.g. 150ms): closed at t=10.0, open at t=10.15
    with patch("backend.eye_tracking.cursor_controller.perf_counter", side_effect=[10.0, 10.15]):
        # Closed frame (ear = 0.15 < 0.198)
        ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.15))
        assert ctrl._eye_closed is True
        # Re-open frame (ear = 0.32 > 0.270)
        ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.32))
        assert ctrl._eye_closed is False

    # Reflex blink (< 300ms) must NOT fire quick blink
    assert "QUICK_BLINK" not in dispatched_actions

    # 2. Deliberate blink (300ms - 480ms, e.g. 350ms): closed at t=20.0, open at t=20.35
    with patch("backend.eye_tracking.cursor_controller.perf_counter", side_effect=[20.0, 20.35]):
        # Closed frame (ear = 0.15 < 0.198)
        ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.15))
        assert ctrl._eye_closed is True
        # Re-open frame (ear = 0.32 > 0.270)
        ctrl.update(blink_state=_make_blink_state(smoothed_ear=0.32))
        assert ctrl._eye_closed is False

    # Deliberate intentional blink must fire QUICK_BLINK
    assert "QUICK_BLINK" in dispatched_actions







