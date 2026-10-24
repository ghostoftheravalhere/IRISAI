"""Unit and integration tests for 16-point polynomial calibration, validation gates, and cursor safety."""

from __future__ import annotations

import math
import sys
from types import ModuleType
from unittest.mock import MagicMock

# Ensure cv2 and mediapipe can be imported if running in minimal headless environments
if "cv2" not in sys.modules:
    fake_cv2 = ModuleType("cv2")
    fake_cv2.__version__ = "4.10.0"
    sys.modules["cv2"] = fake_cv2

if "mediapipe" not in sys.modules:
    mediapipe = ModuleType("mediapipe")
    mediapipe.solutions = ModuleType("mediapipe.solutions")
    sys.modules["mediapipe"] = mediapipe
    sys.modules["mediapipe.solutions"] = mediapipe.solutions

import numpy as np
import pytest

from backend.eye_tracking.calibration import (
    CalibrationCaptureError,
    CalibrationPoint,
    CalibrationSample,
    EyeCalibrationService,
    EyeCenter,
    ValidationReport,
)
from backend.eye_tracking.cursor_controller import (
    CursorController,
    CursorControllerConfig,
)
from backend.eye_tracking.eye_interaction_config import EyeInteractionConfig
from backend.eye_tracking.face_mesh_service import (
    LEFT_EYE_LANDMARK_INDICES,
    RIGHT_EYE_LANDMARK_INDICES,
    EyeData,
    NormalizedLandmark,
)
from backend.vision.calibration_engine import (
    FOUR_POINT_VALIDATION_GRID,
    NINE_POINT_GRID,
    SIXTEEN_POINT_GRID,
    CalibrationDataPoint,
    PolynomialCalibrator,
    PolynomialGazeModel,
)

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
    """Build eye landmarks with valid EAR geometry around (cx, cy)."""
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


def _make_eye_data(*, cx: float, cy: float, open_eye: bool = True) -> EyeData:
    """Create synthetic binocular eye data centered near (cx, cy)."""
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


class DummyGaze:
    def __init__(self, x: float, y: float, is_calibrated: bool = True):
        self.x = x
        self.y = y
        self.raw_x = x
        self.raw_y = y
        self.is_calibrated = is_calibrated


# =========================================================================
# 1. Synthetic quadratic mapping recovery
# =========================================================================

def test_synthetic_quadratic_mapping_recovery():
    """Verify that a known quadratic polynomial mapping is recovered with high precision."""
    # Synthetic quadratic parameters:
    # Target X = 0.1 + 0.8*u - 0.05*v + 0.12*u^2 - 0.08*v^2 + 0.04*u*v
    # Target Y = 0.05 - 0.03*u + 0.85*v - 0.06*u^2 + 0.10*v^2 - 0.02*u*v
    calibrator = PolynomialCalibrator(max_condition_number=10000.0)

    samples = []
    for u, v in SIXTEEN_POINT_GRID:
        tx = 0.1 + 0.8 * u - 0.05 * v + 0.12 * (u ** 2) - 0.08 * (v ** 2) + 0.04 * u * v
        ty = 0.05 - 0.03 * u + 0.85 * v - 0.06 * (u ** 2) + 0.10 * (v ** 2) - 0.02 * u * v
        samples.append(CalibrationDataPoint(target_x=tx, target_y=ty, pupil_x=u, pupil_y=v))

    result = calibrator.fit(samples)

    assert result.rank == 6, f"Expected rank 6, got {result.rank}"
    assert result.condition_number <= 10000.0
    assert result.r2_score > 0.999, f"Expected R^2 > 0.999, got {result.r2_score}"
    assert result.rmse < 0.005, f"Expected RMSE < 0.005, got {result.rmse}"

    # Test prediction on unseen intermediate coordinates
    unseen_points = [(0.25, 0.25), (0.50, 0.50), (0.75, 0.75), (0.35, 0.65)]
    for u, v in unseen_points:
        expected_x = 0.1 + 0.8 * u - 0.05 * v + 0.12 * (u ** 2) - 0.08 * (v ** 2) + 0.04 * u * v
        expected_y = 0.05 - 0.03 * u + 0.85 * v - 0.06 * (u ** 2) + 0.10 * (v ** 2) - 0.02 * u * v
        pred_x, pred_y = calibrator.predict(u, v)
        assert math.isclose(pred_x, expected_x, abs_tol=0.005)
        assert math.isclose(pred_y, expected_y, abs_tol=0.005)


# =========================================================================
# 2. Consistent prediction after input standardization
# =========================================================================

def test_consistent_prediction_after_input_standardization():
    """Verify standardization statistics are stored and predictions remain invariant to linear domain scale/shift."""
    model = PolynomialGazeModel()

    # Shift and scale domain: u' = 50.0 * u + 10.0, v' = 100.0 * v - 25.0
    raw_samples = []
    scaled_samples = []
    for u, v in SIXTEEN_POINT_GRID:
        tx = 0.9 * u + 0.1 * (v ** 2)
        ty = 0.85 * v + 0.15 * (u * v)
        raw_samples.append(CalibrationDataPoint(target_x=tx, target_y=ty, pupil_x=u, pupil_y=v))
        u_prime = 50.0 * u + 10.0
        v_prime = 100.0 * v - 25.0
        scaled_samples.append(CalibrationDataPoint(target_x=tx, target_y=ty, pupil_x=u_prime, pupil_y=v_prime))

    raw_fit = model.fit(raw_samples)
    raw_pred_x, raw_pred_y = model.predict(0.5, 0.5)

    scaled_fit = model.fit(scaled_samples)
    assert scaled_fit.mean_u is not None and scaled_fit.std_u is not None
    assert scaled_fit.mean_v is not None and scaled_fit.std_v is not None
    # Verify standard deviations captured the 50x and 100x scaling
    assert math.isclose(scaled_fit.std_u / raw_fit.std_u, 50.0, rel_tol=1e-3)
    assert math.isclose(scaled_fit.std_v / raw_fit.std_v, 100.0, rel_tol=1e-3)

    # Predicting with transformed inputs must produce the identical target coordinates
    test_u_prime = 50.0 * 0.5 + 10.0
    test_v_prime = 100.0 * 0.5 - 25.0
    scaled_pred_x, scaled_pred_y = model.predict(test_u_prime, test_v_prime)

    assert math.isclose(raw_pred_x, scaled_pred_x, abs_tol=1e-4)
    assert math.isclose(raw_pred_y, scaled_pred_y, abs_tol=1e-4)


def test_near_zero_variance_standardization_fallback():
    """Verify near-zero standard deviation falls back safely to 1.0 without division by zero or NaN."""
    model = PolynomialGazeModel()
    # All points have identical pupil_x, but varied pupil_y
    samples = [
        CalibrationDataPoint(target_x=float(i) / 10.0, target_y=float(i) / 10.0, pupil_x=0.5, pupil_y=float(i) / 10.0)
        for i in range(10)
    ]
    # Because pupil_x is constant, design matrix will be rank deficient (< 6)
    with pytest.raises(ValueError, match=r"rank[- ]deficient"):
        model.fit(samples)

    assert model.is_fitted is False
    assert model.fitted_model is None


# =========================================================================
# 3. Non-finite input rejection
# =========================================================================

def test_non_finite_input_rejection():
    """Verify non-finite inputs (NaN, inf) are strictly rejected during fitting."""
    model = PolynomialGazeModel()

    bad_samples = [
        CalibrationDataPoint(target_x=0.5, target_y=0.5, pupil_x=float("nan"), pupil_y=0.5),
        CalibrationDataPoint(target_x=0.5, target_y=0.5, pupil_x=0.5, pupil_y=float("inf")),
        CalibrationDataPoint(target_x=float("-inf"), target_y=0.5, pupil_x=0.5, pupil_y=0.5),
        CalibrationDataPoint(target_x=0.5, target_y=float("nan"), pupil_x=0.5, pupil_y=0.5),
    ]

    for bad in bad_samples:
        samples = [CalibrationDataPoint(target_x=0.1 * i, target_y=0.1 * i, pupil_x=0.1 * i, pupil_y=0.1 * i) for i in range(16)]
        samples[3] = bad
        with pytest.raises(ValueError, match="non-finite"):
            model.fit(samples)
        assert model.is_fitted is False
        assert model.fitted_model is None


# =========================================================================
# 4. Rank-deficient data rejection
# =========================================================================

def test_rank_deficient_data_rejection():
    """Verify fitting rejects rank-deficient design matrices (< 6 independent features)."""
    model = PolynomialGazeModel()

    # 1. Fewer than 6 samples
    underdetermined = [
        CalibrationDataPoint(target_x=0.1 * i, target_y=0.1 * i, pupil_x=0.1 * i, pupil_y=0.1 * i)
        for i in range(5)
    ]
    with pytest.raises(ValueError, match=r"(?i)at least 6"):
        model.fit(underdetermined)

    # 2. 16 samples that are strictly collinear (v = 2 * u) -> rank < 6
    collinear = [
        CalibrationDataPoint(target_x=0.05 * i, target_y=0.05 * i, pupil_x=0.05 * i, pupil_y=0.10 * i)
        for i in range(16)
    ]
    with pytest.raises(ValueError, match=r"rank[- ]deficient"):
        model.fit(collinear)

    assert model.is_fitted is False
    assert model.fitted_model is None


# =========================================================================
# 5. Ill-conditioned fit rejection
# =========================================================================

def test_ill_conditioned_fit_rejection():
    """Verify fitting rejects excessively ill-conditioned matrices exceeding max_condition_number."""
    # 1. Reject fit when design matrix condition number exceeds configured threshold
    strict_model = PolynomialGazeModel(max_condition_number=3.0)
    samples = [CalibrationDataPoint(target_x=u, target_y=v, pupil_x=u, pupil_y=v) for u, v in SIXTEEN_POINT_GRID]
    with pytest.raises(ValueError, match="ill-conditioned"):
        strict_model.fit(samples)

    assert strict_model.is_fitted is False
    assert strict_model.fitted_model is None

    # 2. Reject fit with default max_condition_number=10000.0 when data is nearly collinear
    default_model = PolynomialGazeModel(max_condition_number=10000.0)
    ill_conditioned = [
        CalibrationDataPoint(target_x=u, target_y=v, pupil_x=u, pupil_y=v)
        for u, v in [(0.1, 0.1), (0.9, 0.1), (0.5, 0.5), (0.1, 0.9), (0.9, 0.9), (0.5, 0.501)]
    ]
    with pytest.raises(ValueError, match="ill-conditioned"):
        default_model.fit(ill_conditioned)

    assert default_model.is_fitted is False
    assert default_model.fitted_model is None


# =========================================================================
# 6. Validation targets remaining separate from training data
# =========================================================================

def test_validation_targets_remain_separate_from_training_data():
    """Verify 16-point training samples and 4 validation samples are stored in isolated collections."""
    config = EyeInteractionConfig(calibration_mode="16-point")
    service = EyeCalibrationService(eye_config=config)

    assert len(service.training_points) == 16
    assert len(service.validation_points) == 4

    # 1. Feed 16 training targets
    for i in range(16):
        pt = service.get_progress().current_point
        assert pt is not None
        assert service.get_progress().phase == "training"
        frames = [_make_eye_data(cx=pt.x, cy=pt.y) for _ in range(20)]
        service.add_sample(frames)

    assert len(service._samples) == 16
    assert len(service._validation_samples) == 0
    assert service.get_progress().phase == "validation"

    # 2. Feed 4 validation targets
    for i in range(4):
        pt = service.get_progress().current_point
        assert pt is not None
        assert service.get_progress().phase == "validation"
        frames = [_make_eye_data(cx=pt.x, cy=pt.y) for _ in range(20)]
        service.add_sample(frames)

    # CRITICAL: Training sample list must remain exactly 16; validation samples must be 4
    assert len(service._samples) == 16
    assert len(service._validation_samples) == 4
    assert service.get_progress().phase in ("complete", "failed")


# =========================================================================
# 7. Mean and maximum error gates
# =========================================================================

def test_validation_error_gates():
    """Verify acceptance thresholds: mean <= 0.08 and max <= 0.15."""
    calibrator = PolynomialCalibrator()

    # Fit identity mapping
    samples = [
        CalibrationDataPoint(target_x=u, target_y=v, pupil_x=u, pupil_y=v)
        for u, v in SIXTEEN_POINT_GRID
    ]
    calibrator.fit(samples)

    # Case A: Validation points perfectly aligned (errors ~ 0)
    good_val = [
        CalibrationDataPoint(target_x=u, target_y=v, pupil_x=u, pupil_y=v)
        for u, v in FOUR_POINT_VALIDATION_GRID
    ]
    metrics_good = calibrator.evaluate_samples(good_val, screen_width=1920, screen_height=1080)
    assert metrics_good["mean_norm_error"] <= 0.08
    assert metrics_good["max_norm_error"] <= 0.15

    # Case B: High mean error (> 0.08)
    bad_mean_val = [
        CalibrationDataPoint(target_x=u, target_y=v, pupil_x=u + 0.10, pupil_y=v + 0.10)
        for u, v in FOUR_POINT_VALIDATION_GRID
    ]
    metrics_bad_mean = calibrator.evaluate_samples(bad_mean_val, screen_width=1920, screen_height=1080)
    assert metrics_bad_mean["mean_norm_error"] > 0.08

    # Case C: Mean error is low (0.04 <= 0.08), but a single outlier target has max error 0.18 (> 0.15)
    outlier_val = [
        CalibrationDataPoint(target_x=FOUR_POINT_VALIDATION_GRID[0][0], target_y=FOUR_POINT_VALIDATION_GRID[0][1], pupil_x=FOUR_POINT_VALIDATION_GRID[0][0], pupil_y=FOUR_POINT_VALIDATION_GRID[0][1]),
        CalibrationDataPoint(target_x=FOUR_POINT_VALIDATION_GRID[1][0], target_y=FOUR_POINT_VALIDATION_GRID[1][1], pupil_x=FOUR_POINT_VALIDATION_GRID[1][0], pupil_y=FOUR_POINT_VALIDATION_GRID[1][1]),
        CalibrationDataPoint(target_x=FOUR_POINT_VALIDATION_GRID[2][0], target_y=FOUR_POINT_VALIDATION_GRID[2][1], pupil_x=FOUR_POINT_VALIDATION_GRID[2][0], pupil_y=FOUR_POINT_VALIDATION_GRID[2][1]),
        CalibrationDataPoint(target_x=FOUR_POINT_VALIDATION_GRID[3][0], target_y=FOUR_POINT_VALIDATION_GRID[3][1], pupil_x=FOUR_POINT_VALIDATION_GRID[3][0] + 0.18, pupil_y=FOUR_POINT_VALIDATION_GRID[3][1]),
    ]
    metrics_outlier = calibrator.evaluate_samples(outlier_val, screen_width=1920, screen_height=1080)
    assert metrics_outlier["mean_norm_error"] <= 0.08
    assert metrics_outlier["max_norm_error"] > 0.15  # Outlier gate fails


# =========================================================================
# 8. Failed-fit and failed-validation authorization
# =========================================================================

def test_failed_fit_and_failed_validation_authorization():
    """Verify calibration is never authorized if fit fails or validation gates fail."""
    config = EyeInteractionConfig(
        calibration_mode="16-point",
        validation_mean_norm_threshold=0.08,
        validation_max_norm_threshold=0.15,
    )
    service = EyeCalibrationService(eye_config=config)

    # 1. Complete training with valid points
    for u, v in SIXTEEN_POINT_GRID:
        frames = [_make_eye_data(cx=u, cy=v) for _ in range(20)]
        service.add_sample(frames)

    assert service._polynomial_calibrator is not None
    assert service._polynomial_calibrator.is_fitted is True

    # 2. Provide bad validation targets (simulating severe eye drift: shifted by 0.12 inward)
    for u, v in FOUR_POINT_VALIDATION_GRID:
        frames = [_make_eye_data(cx=u * 0.7 + 0.15, cy=v * 0.7 + 0.15) for _ in range(20)]
        service.add_sample(frames)

    # Validation must fail and is_calibrated must be strictly False
    assert service.get_progress().phase == "failed"
    assert service.is_calibrated is False
    assert service._complete is False
    assert service._validation_report is not None
    assert service._validation_report.passed is False


# =========================================================================
# 9. Retry behavior without target advancement
# =========================================================================

def test_retry_behavior_without_target_advancement():
    """Verify failed frame capture rejects the attempt and does not advance the target index."""
    config = EyeInteractionConfig(
        calibration_min_valid_samples=15,
        calibration_blink_ear_threshold=0.18,
    )
    service = EyeCalibrationService(eye_config=config)

    initial_point = service.get_progress().current_point
    initial_completed = service.get_progress().completed_points

    # Attempt capture with closed eyes (blinks: EAR < 0.18) -> fails minimum valid samples
    blink_frames = [_make_eye_data(cx=0.5, cy=0.5, open_eye=False) for _ in range(25)]

    with pytest.raises(CalibrationCaptureError, match=r"stable samples"):
        service.add_sample(blink_frames)

    # Target index must NOT advance
    assert service.get_progress().completed_points == initial_completed
    assert service.get_progress().current_point == initial_point
    assert len(service._samples) == 0

    # Retry with valid open eye frames -> succeeds and advances
    valid_frames = [_make_eye_data(cx=initial_point.x, cy=initial_point.y, open_eye=True) for _ in range(20)]
    progress = service.add_sample(valid_frames)

    assert progress.completed_points == initial_completed + 1
    assert len(service._samples) == 1


# =========================================================================
# 10. Reset integrity
# =========================================================================

def test_reset_integrity_clears_all_state():
    """Verify reset/restart clears all samples, mappings, validation reports, and authorization."""
    config = EyeInteractionConfig(calibration_mode="16-point")
    service = EyeCalibrationService(eye_config=config)

    # Complete 16 training + 4 validation
    for u, v in SIXTEEN_POINT_GRID:
        service.add_sample([_make_eye_data(cx=u, cy=v) for _ in range(20)])
    for u, v in FOUR_POINT_VALIDATION_GRID:
        service.add_sample([_make_eye_data(cx=u, cy=v) for _ in range(20)])

    assert service.is_calibrated is True
    assert service._polynomial_calibrator is not None

    # Reset
    service.reset()

    assert len(service._samples) == 0
    assert len(service._validation_samples) == 0
    assert len(service._validation_sample_counts) == 0
    assert service._mapping is None
    assert service._polynomial_calibrator is None
    assert service._quality is None
    assert service._validation_report is None
    assert service.is_calibrated is False
    assert service._complete is False
    assert service._phase == "training"
    assert service.get_progress().completed_points == 0
    assert service.get_progress().current_point is not None


# =========================================================================
# 11. Cursor dropout rejection and safe reacquisition
# =========================================================================

def test_cursor_prediction_validation_and_dropout_rejection():
    """Verify cursor controller rejects None, NaN, inf, and coordinates outside [-0.15, 1.15]."""
    # 1. Test static validator
    assert CursorController._is_valid_prediction(None) is False
    assert CursorController._is_valid_prediction(DummyGaze(float("nan"), 0.5)) is False
    assert CursorController._is_valid_prediction(DummyGaze(0.5, float("inf"))) is False
    assert CursorController._is_valid_prediction(DummyGaze(-0.16, 0.5)) is False
    assert CursorController._is_valid_prediction(DummyGaze(0.5, 1.16)) is False
    assert CursorController._is_valid_prediction(DummyGaze(-0.15, 0.5)) is True
    assert CursorController._is_valid_prediction(DummyGaze(1.15, 1.15)) is True
    assert CursorController._is_valid_prediction(DummyGaze(0.5, 0.5)) is True


def test_cursor_dropout_grace_and_reacquisition_without_teleportation():
    """Verify out-of-bounds predictions trigger tracking dropout without edge-clamping or teleportation."""
    config = CursorControllerConfig()
    gaze_svc = MagicMock()
    cursor = CursorController(config=config, gaze_service=gaze_svc)
    mock_pyautogui = MagicMock()
    mock_pyautogui.position.return_value = (960, 540)
    cursor._load_pyautogui = lambda: mock_pyautogui
    cursor._pyautogui = mock_pyautogui
    cursor.enable()

    # Step 1: Valid center gaze
    gaze_svc.get_latest_gaze.return_value = DummyGaze(0.5, 0.5)
    state1 = cursor.update(tracking_confidence=0.9, face_detected=True)
    assert state1.trackingActive is True
    assert cursor._dropout_frames == 0

    # Step 2: Feed out-of-bounds prediction (e.g. 1.30, 0.50) -> triggers dropout coasting
    gaze_svc.get_latest_gaze.return_value = DummyGaze(1.30, 0.50)
    state2 = cursor.update(tracking_confidence=0.9, face_detected=True)
    assert cursor._dropout_frames == 1
    # Still tracking active during grace period (<= 5 frames)
    assert state2.trackingActive is True

    # Step 3: Continue feeding out-of-bounds until grace period expires (> 5 frames)
    for _ in range(6):
        cursor.update(tracking_confidence=0.9, face_detected=True)

    state_lost = cursor.get_state()
    # Tracking lost; drag released; no clamping to screen edges
    assert state_lost.trackingActive is False
    assert cursor._recovery_frames_remaining > 0

    # Step 4: Reacquisition with valid gaze -> smooth recovery frames without teleportation
    gaze_svc.get_latest_gaze.return_value = DummyGaze(0.5, 0.5)
    state_rec = cursor.update(tracking_confidence=0.9, face_detected=True)
    assert state_rec.trackingActive is True
