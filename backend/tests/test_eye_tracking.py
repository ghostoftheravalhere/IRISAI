"""Unit tests for eye calibration sampling and quality scoring."""

from __future__ import annotations

import sys
from types import ModuleType

# Keep these tests runnable without OpenCV/MediaPipe installed in the env.
try:
    import cv2
except ImportError:
    if "cv2" not in sys.modules:
        fake_cv2 = ModuleType("cv2")
        fake_cv2.__version__ = "4.10.0"
        sys.modules["cv2"] = fake_cv2
else:
    if not hasattr(cv2, "__version__"):
        cv2.__version__ = "4.10.0"

if "mediapipe" not in sys.modules:
    mediapipe = ModuleType("mediapipe")
    mediapipe.solutions = ModuleType("mediapipe.solutions")
    sys.modules["mediapipe"] = mediapipe
    sys.modules["mediapipe.solutions"] = mediapipe.solutions

import pytest

from backend.eye_tracking.calibration import (
    CalibrationCaptureError,
    CalibrationPoint,
    CalibrationSample,
    EyeCalibrationService,
    EyeCenter,
)
from backend.eye_tracking.eye_interaction_config import EyeInteractionConfig
from backend.eye_tracking.face_mesh_service import (
    LEFT_EYE_LANDMARK_INDICES,
    RIGHT_EYE_LANDMARK_INDICES,
    EyeData,
    NormalizedLandmark,
)

# MediaPipe EAR landmark order used by EyeCalibrationService.
_RIGHT_EAR = (33, 160, 158, 133, 153, 144)
_LEFT_EAR = (362, 385, 387, 263, 373, 380)


def _landmarks_for_eye(
    indices: tuple[int, ...],
    ear_indices: tuple[int, int, int, int, int, int],
    *,
    cx: float,
    cy: float,
    open_eye: bool = True,
) -> tuple[NormalizedLandmark, ...]:
    """Build eye landmarks with valid EAR geometry around ``(cx, cy)``."""
    half_width = 0.020
    half_height = 0.012 if open_eye else 0.002
    p1, p2, p3, p4, p5, p6 = ear_indices
    positioned = {
        p1: (cx - half_width, cy),
        p4: (cx + half_width, cy),
        p2: (cx - half_width * 0.35, cy - half_height),
        p3: (cx + half_width * 0.35, cy - half_height),
        p6: (cx - half_width * 0.35, cy + half_height),
        p5: (cx + half_width * 0.35, cy + half_height),
    }

    points: list[NormalizedLandmark] = []
    for index in indices:
        x, y = positioned.get(index, (cx, cy))
        points.append(NormalizedLandmark(index=index, x=x, y=y, z=0.0))
    return tuple(points)


def _eye_data(*, cx: float, cy: float, open_eye: bool = True) -> EyeData:
    """Create synthetic binocular eye data centered near ``(cx, cy)``."""
    return EyeData(
        left_eye=_landmarks_for_eye(
            LEFT_EYE_LANDMARK_INDICES,
            _LEFT_EAR,
            cx=cx + 0.02,
            cy=cy,
            open_eye=open_eye,
        ),
        right_eye=_landmarks_for_eye(
            RIGHT_EYE_LANDMARK_INDICES,
            _RIGHT_EAR,
            cx=cx - 0.02,
            cy=cy,
            open_eye=open_eye,
        ),
    )


def test_aggregate_stable_samples_averages_and_rejects_outliers() -> None:
    """Multi-sample capture should average inliers and drop jump/outlier frames."""
    config = EyeInteractionConfig(
        calibration_min_valid_samples=8,
        calibration_outlier_mad_scale=2.5,
        calibration_max_center_jump=0.035,
        calibration_max_sample_dispersion=0.02,
    )
    service = EyeCalibrationService(eye_config=config)

    samples = [_eye_data(cx=0.50, cy=0.45) for _ in range(20)]
    samples[5] = _eye_data(cx=0.62, cy=0.45)  # sudden jump
    samples[8] = _eye_data(cx=0.50, cy=0.45, open_eye=False)  # blink

    averaged, center, accepted = service._aggregate_stable_samples(samples)

    assert accepted >= config.calibration_min_valid_samples
    assert abs(center.x - 0.50) < 0.01
    assert abs(center.y - 0.45) < 0.01
    assert len(averaged.left_eye) == len(LEFT_EYE_LANDMARK_INDICES)


def test_aggregate_rejects_unstable_dispersion() -> None:
    """Wandering gaze should fail capture instead of writing a noisy point."""
    config = EyeInteractionConfig(
        calibration_min_valid_samples=8,
        calibration_max_sample_dispersion=0.005,
        calibration_max_center_jump=0.05,
    )
    service = EyeCalibrationService(eye_config=config)
    samples = [
        _eye_data(cx=0.50 + ((index % 5) - 2) * 0.008, cy=0.45)
        for index in range(20)
    ]

    with pytest.raises(CalibrationCaptureError, match="dispersion"):
        service._aggregate_stable_samples(samples)


def test_quality_score_formula_and_thresholds() -> None:
    """Score math is unchanged; labels reflect webcam cursor usability bands."""
    config = EyeInteractionConfig(
        calibration_rmse_scale=5.0,
        calibration_quality_threshold=0.45,
        calibration_good_score_threshold=0.58,
    )
    service = EyeCalibrationService(eye_config=config)

    perfect_samples = [
        CalibrationSample(
            point=CalibrationPoint(index=index, x=x, y=y),
            eye_data=_eye_data(cx=x, cy=y),
            eye_center=EyeCenter(x=x, y=y),
            captured_at=0.0,
        )
        for index, (x, y) in enumerate(
            [
                (0.1, 0.1),
                (0.5, 0.1),
                (0.9, 0.1),
                (0.1, 0.5),
                (0.5, 0.5),
                (0.9, 0.5),
                (0.1, 0.9),
                (0.5, 0.9),
                (0.9, 0.9),
            ]
        )
    ]
    quality = service._evaluate_quality(
        samples=perfect_samples,
        x_coefficients=(1.0, 0.0, 0.0),
        y_coefficients=(0.0, 1.0, 0.0),
    )
    assert quality.rmse == pytest.approx(0.0)
    assert quality.score == pytest.approx(1.0)
    assert quality.label == "good"
    assert quality.recommend_recalibration is False

    # Constant residual length ≈ 0.10 → score = 1/(1+0.5) ≈ 0.667 (good for webcam).
    offset_x = 0.07
    offset_y = 0.071418485
    noisy = [
        CalibrationSample(
            point=sample.point,
            eye_data=sample.eye_data,
            eye_center=EyeCenter(
                x=sample.eye_center.x + offset_x,
                y=sample.eye_center.y + offset_y,
            ),
            captured_at=0.0,
        )
        for sample in perfect_samples
    ]
    quality = service._evaluate_quality(
        samples=noisy,
        x_coefficients=(1.0, 0.0, 0.0),
        y_coefficients=(0.0, 1.0, 0.0),
    )
    assert quality.rmse == pytest.approx(0.10, abs=0.001)
    assert quality.score == pytest.approx(1.0 / (1.0 + 0.10 * 5.0), abs=0.005)
    assert quality.label == "good"
    assert quality.recommend_recalibration is False

    # Typical reported webcam residual ≈ score 0.48 → fair / usable, not poor.
    fair = service._evaluate_quality(
        samples=[
            CalibrationSample(
                point=sample.point,
                eye_data=sample.eye_data,
                eye_center=EyeCenter(
                    x=sample.eye_center.x + 0.153,
                    y=sample.eye_center.y + 0.153,
                ),
                captured_at=0.0,
            )
            for sample in perfect_samples
        ],
        x_coefficients=(1.0, 0.0, 0.0),
        y_coefficients=(0.0, 1.0, 0.0),
    )
    assert fair.score == pytest.approx(0.48, abs=0.02)
    assert fair.label == "fair"
    assert fair.recommend_recalibration is False


def test_gaze_confidence_does_not_collapse_from_clamped_jitter() -> None:
    """Out-of-range raw mapping should soften confidence, not invent huge jitter."""
    from backend.eye_tracking.gaze_service import EyeGazeService

    confidence = EyeGazeService._compute_confidence(  # type: ignore[arg-type]
        object.__new__(EyeGazeService),
        raw_x=1.4,
        raw_y=0.5,
        smoothed_x=1.0,
        smoothed_y=0.5,
        calibration_score=0.7,
    )
    # Previous formula used raw vs clamped EMA → stability 0 and confidence ~0.31.
    assert confidence >= 0.40


def test_point_7_downgaze_sample_acceptance() -> None:
    """Downgaze eye frames with natural eyelid excursion (EAR ~0.24) must be accepted."""
    config = EyeInteractionConfig()
    service = EyeCalibrationService(eye_config=config)

    # Build 20 downgaze frames with EAR ~0.24 (half_height = 0.0096)
    downgaze_samples = []
    for _ in range(20):
        left_eye = _landmarks_for_eye(
            LEFT_EYE_LANDMARK_INDICES,
            _LEFT_EAR,
            cx=0.12,
            cy=0.88,
            open_eye=True,
        )
        right_eye = _landmarks_for_eye(
            RIGHT_EYE_LANDMARK_INDICES,
            _RIGHT_EAR,
            cx=0.08,
            cy=0.88,
            open_eye=True,
        )
        downgaze_samples.append(EyeData(left_eye=left_eye, right_eye=right_eye))

    # All 20 frames should be valid
    assert all(service._is_valid_calibration_frame(s) for s in downgaze_samples)

    # Point 7 should aggregate and record successfully
    # Simulate first 6 points recorded
    for i in range(6):
        pt = service.points[i]
        s = [_eye_data(cx=pt.x, cy=pt.y) for _ in range(20)]
        service.record_current_point_from_samples(s)

    prog_before = service.get_progress()
    assert prog_before.completed_points == 6
    assert prog_before.current_point.index == 6  # Point 7

    prog_after = service.record_current_point_from_samples(downgaze_samples)
    assert prog_after.completed_points == 7
    assert prog_after.current_point.index == 7  # Advanced to Point 8


def test_point_specific_retry_preserves_previous_points() -> None:
    """Failing a point capture must preserve earlier points and allow retry."""
    config = EyeInteractionConfig()
    service = EyeCalibrationService(eye_config=config)

    # Complete Points 1-6
    for i in range(6):
        pt = service.points[i]
        service.record_current_point_from_samples([_eye_data(cx=pt.x, cy=pt.y) for _ in range(20)])

    assert service.get_progress().completed_points == 6
    assert service.get_progress().current_point.index == 6  # Point 7

    # Attempt capture with empty / invalid samples (simulating movement/timeout)
    with pytest.raises(CalibrationCaptureError):
        service.record_current_point_from_samples([])

    # Verify Points 1-6 remain completely intact
    prog = service.get_progress()
    assert prog.completed_points == 6
    assert prog.current_point.index == 6  # Still on Point 7

    # Retry Point 7 with valid samples
    pt7 = service.points[6]
    valid_pt7_samples = [_eye_data(cx=pt7.x, cy=pt7.y) for _ in range(20)]
    prog_retry = service.record_current_point_from_samples(valid_pt7_samples)

    assert prog_retry.completed_points == 7
    assert prog_retry.current_point.index == 7  # Advanced to Point 8


def test_all_9_points_full_calibration_flow() -> None:
    """All 9 points must record and compute valid mapping with dynamic RMSE."""
    config = EyeInteractionConfig()
    service = EyeCalibrationService(eye_config=config)

    for i in range(9):
        pt = service.points[i]
        samples = [_eye_data(cx=pt.x * 0.3 + 0.35 + 0.001 * (i % 3), cy=pt.y * 0.3 + 0.35) for _ in range(20)]
        prog = service.record_current_point_from_samples(samples)

    final_prog = service.get_progress()
    assert final_prog.complete is True
    assert final_prog.completed_points == 9
    assert final_prog.quality is not None
    assert final_prog.quality.score > 0.50
    assert final_prog.quality.rmse >= 0.0
    assert service.get_mapping() is not None


def test_optimized_eye_config_defaults() -> None:
    """Verify optimized eye interaction thresholds for snappier clicking and responsiveness."""
    config = EyeInteractionConfig()
    assert config.intentional_blink_min_ms == 400.0
    assert config.cursor_smoothing_alpha == 0.20
    assert config.cursor_dead_zone_px == 15.0


def test_cursor_controller_triggers_click_feedback() -> None:
    """Verify pointer action execution triggers the click feedback pop-up."""
    from unittest.mock import MagicMock, patch
    from backend.eye_tracking.action_engine import ActionState, ActionType
    from backend.eye_tracking.cursor_controller import CursorController

    mock_gaze = MagicMock()
    controller = CursorController(gaze_service=mock_gaze)
    mock_pyautogui = MagicMock()

    action_state = ActionState(
        action=ActionType.LEFT_CLICK,
        timestamp=123.456,
        sourceGesture=MagicMock(),
        sourceGestureTimestamp=123.400,
        cursorPaused=False,
        dragMode=False,
        cooldownActive=False,
    )

    with patch("backend.eye_tracking.click_feedback_overlay.show_click_feedback_popup") as mock_popup:
        controller._last_action_timestamp = 123.456
        controller._last_x = 400
        controller._last_y = 300
        controller._execute_pointer_action(mock_pyautogui, action_state)

        mock_pyautogui.click.assert_called_once_with(button="left")
        mock_popup.assert_called_once_with(text="Left Click", duration_ms=900, x=400, y=300)


