"""Unit tests for 9-Point Polynomial Calibration Engine & Head-Pose Compensation."""

from __future__ import annotations

import math
import numpy as np
import pytest

from backend.vision.calibration_engine import (
    NINE_POINT_GRID,
    CalibrationDataPoint,
    HeadPoseAnchor,
    PolynomialCalibrator,
    PolynomialMappingResult,
)
from backend.vision.head_pose import HeadPose


def test_nine_point_grid_definition():
    """Verify standard 9-point grid has 9 distinct points within normalized range."""
    assert len(NINE_POINT_GRID) == 9
    for x, y in NINE_POINT_GRID:
        assert 0.0 <= x <= 1.0
        assert 0.0 <= y <= 1.0


def test_polynomial_fitting_accuracy_on_nonlinear_data():
    """Verify 2nd-degree polynomial calibrator fits quadratic distortion accurately."""
    calibrator = PolynomialCalibrator()

    # Create synthetic non-linear ground truth mapping
    # Screen = a0 + a1*px + a2*py + a3*px^2 + a4*py^2 + a5*px*py
    samples = []
    for tx, ty in NINE_POINT_GRID:
        # Inverse distorted pupil position: px = tx - 0.15*tx^2, py = ty + 0.1*ty^2
        px = tx - 0.12 * (tx ** 2) + 0.05 * (ty ** 2)
        py = ty + 0.08 * (ty ** 2) - 0.03 * (tx * ty)
        samples.append(
            CalibrationDataPoint(
                target_x=tx,
                target_y=ty,
                pupil_x=px,
                pupil_y=py,
            )
        )

    result = calibrator.fit(samples)
    assert isinstance(result, PolynomialMappingResult)
    assert result.degree == 2
    assert result.sample_count == 9
    assert result.rmse < 0.015, f"Polynomial RMSE should be < 0.015, got {result.rmse}"
    assert result.r2_score > 0.99, f"R^2 score should be > 0.99, got {result.r2_score}"

    # Verify prediction matches targets on calibration samples
    for s in samples:
        pred_x, pred_y = calibrator.predict(s.pupil_x, s.pupil_y)
        assert math.isclose(pred_x, s.target_x, abs_tol=0.02)
        assert math.isclose(pred_y, s.target_y, abs_tol=0.02)


def test_polynomial_vs_linear_error_reduction():
    """Verify polynomial fit achieves lower RMSE than linear fit on non-linear coordinates."""
    calibrator = PolynomialCalibrator()

    # Distorted data with strong curvature
    samples = []
    for tx, ty in NINE_POINT_GRID:
        px = tx + 0.25 * (tx ** 2)
        py = ty + 0.25 * (ty ** 2)
        samples.append(CalibrationDataPoint(target_x=tx, target_y=ty, pupil_x=px, pupil_y=py))

    poly_result = calibrator.fit(samples)

    # Linear baseline fit
    px_arr = np.array([s.pupil_x for s in samples])
    py_arr = np.array([s.pupil_y for s in samples])
    tx_arr = np.array([s.target_x for s in samples])
    ty_arr = np.array([s.target_y for s in samples])

    a_lin = np.column_stack([np.ones_like(px_arr), px_arr, py_arr])
    w_lin_x, _, _, _ = np.linalg.lstsq(a_lin, tx_arr, rcond=None)
    w_lin_y, _, _, _ = np.linalg.lstsq(a_lin, ty_arr, rcond=None)

    lin_pred_x = a_lin @ w_lin_x
    lin_pred_y = a_lin @ w_lin_y
    lin_rmse = float(np.sqrt(np.mean((tx_arr - lin_pred_x) ** 2 + (ty_arr - lin_pred_y) ** 2)))

    # Polynomial RMSE must be substantially smaller than linear RMSE
    assert poly_result.rmse < lin_rmse * 0.25, f"Polynomial RMSE {poly_result.rmse} should be < 25% of linear RMSE {lin_rmse}"


def test_head_pose_anchor_and_drift_compensation():
    """Verify head-pose anchor is captured and deltas are compensated during prediction."""
    calibrator = PolynomialCalibrator(head_comp_yaw=0.01, head_comp_pitch=0.01)

    # Anchor pose: (pitch=10.0, yaw=5.0, roll=0.0)
    anchor_pose = (10.0, 5.0, 0.0)

    samples = []
    for tx, ty in NINE_POINT_GRID:
        samples.append(
            CalibrationDataPoint(
                target_x=tx,
                target_y=ty,
                pupil_x=tx,
                pupil_y=ty,
                head_pose=anchor_pose,
            )
        )

    result = calibrator.fit(samples)
    assert result.anchor_pose is not None
    assert math.isclose(result.anchor_pose.pitch, 10.0, abs_tol=1e-3)
    assert math.isclose(result.anchor_pose.yaw, 5.0, abs_tol=1e-3)

    # Test prediction with shifted head pose: Yaw shifted by +10 deg, causing pupil to shift by +0.10
    # Because pupil drifted by +0.10, head compensation should subtract 0.01 * 10 = 0.10 and recover target!
    shifted_pose = (10.0, 15.0, 0.0)
    drifted_pupil_x = 0.5 + (0.01 * 10.0)  # 0.60
    drifted_pupil_y = 0.5

    pred_x, pred_y = calibrator.predict(drifted_pupil_x, drifted_pupil_y, current_head_pose=shifted_pose)
    assert math.isclose(pred_x, 0.5, abs_tol=0.03), f"Expected compensated pred_x ~ 0.5, got {pred_x}"
    assert math.isclose(pred_y, 0.5, abs_tol=0.03), f"Expected compensated pred_y ~ 0.5, got {pred_y}"


def test_insufficient_samples_raises_error():
    """Verify ValueError is raised when fitting with fewer than 3 samples."""
    calibrator = PolynomialCalibrator()
    samples = [
        CalibrationDataPoint(0.1, 0.1, 0.1, 0.1),
        CalibrationDataPoint(0.5, 0.5, 0.5, 0.5),
    ]
    with pytest.raises(ValueError, match="At least 3 calibration samples"):
        calibrator.fit(samples)


def test_predict_without_fit_raises_error():
    """Verify ValueError is raised when predict() is called before fit()."""
    calibrator = PolynomialCalibrator()
    with pytest.raises(ValueError, match="Calibrator has not been fitted"):
        calibrator.predict(0.5, 0.5)


def test_clamped_screen_predictions():
    """Verify predictions are strictly clamped within [0.0, 1.0]."""
    calibrator = PolynomialCalibrator()
    samples = [
        CalibrationDataPoint(0.0, 0.0, 0.0, 0.0),
        CalibrationDataPoint(0.5, 0.5, 0.5, 0.5),
        CalibrationDataPoint(1.0, 1.0, 1.0, 1.0),
    ]
    calibrator.fit(samples)

    # Inputs far outside normal range
    pred_x, pred_y = calibrator.predict(-5.0, 10.0)
    assert 0.0 <= pred_x <= 1.0
    assert 0.0 <= pred_y <= 1.0
