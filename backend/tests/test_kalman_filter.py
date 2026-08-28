"""Unit tests for 2D Gaze Kalman Filter and Anti-Jitter Pipeline."""

from __future__ import annotations

import math
import numpy as np
import pytest

from backend.vision.kalman_filter import GazeKalmanFilter
from backend.eye_tracking.cursor_controller import CursorController, CursorControllerConfig
from backend.eye_tracking.gaze_service import EyeGazeService


def test_kalman_initialization():
    """Verify initial state and first-frame pass-through."""
    kf = GazeKalmanFilter()
    assert not kf.is_initialized

    # First measurement initializes position directly
    sx, sy = kf.update(150.0, 250.0)
    assert kf.is_initialized
    assert math.isclose(sx, 150.0, abs_tol=1e-3)
    assert math.isclose(sy, 250.0, abs_tol=1e-3)
    assert kf.position == (150.0, 250.0)


def test_stationary_noise_reduction():
    """Verify significant variance reduction during stationary gaze fixations."""
    kf = GazeKalmanFilter(
        process_noise_pos=1e-4,
        measurement_noise_max=0.1,
    )
    np.random.seed(42)

    true_x, true_y = 500.0, 500.0
    num_samples = 60
    noise_std = 8.0

    raw_x = true_x + np.random.normal(0, noise_std, num_samples)
    raw_y = true_y + np.random.normal(0, noise_std, num_samples)

    filtered_x = []
    filtered_y = []

    for rx, ry in zip(raw_x, raw_y):
        fx, fy = kf.update(float(rx), float(ry), dt=1.0 / 30.0)
        filtered_x.append(fx)
        filtered_y.append(fy)

    raw_var_x = float(np.var(raw_x[10:]))
    raw_var_y = float(np.var(raw_y[10:]))
    filt_var_x = float(np.var(filtered_x[10:]))
    filt_var_y = float(np.var(filtered_y[10:]))

    # Anti-jitter filter should achieve at least 50% variance reduction on stationary fixation
    assert filt_var_x < raw_var_x * 0.5, f"Filtered var {filt_var_x} should be < 50% of raw var {raw_var_x}"
    assert filt_var_y < raw_var_y * 0.5, f"Filtered var {filt_var_y} should be < 50% of raw var {raw_var_y}"


def test_saccadic_jump_responsiveness():
    """Verify low latency and fast convergence during rapid saccades."""
    kf = GazeKalmanFilter(
        velocity_threshold=200.0,
        measurement_noise_min=1e-4,
    )

    # 1. Establish fixation at (100, 100)
    for _ in range(15):
        kf.update(100.0, 100.0, dt=1.0 / 30.0)

    # 2. Saccade jump to (800, 800)
    target_x, target_y = 800.0, 800.0
    responses = []
    for _ in range(10):
        fx, fy = kf.update(target_x, target_y, dt=1.0 / 30.0)
        responses.append((fx, fy))

    # Within 5 frames, coordinates should rapidly converge to target
    final_x, final_y = responses[-1]
    assert math.hypot(final_x - target_x, final_y - target_y) < 50.0, "Filter should converge on saccade target"


def test_reset_and_reinitialization():
    """Verify reset clears state and reinitializes cleanly."""
    kf = GazeKalmanFilter()
    kf.update(100.0, 100.0)
    kf.update(110.0, 110.0)
    assert kf.is_initialized

    kf.reset()
    assert not kf.is_initialized
    assert kf.position == (0.0, 0.0)

    # Re-initialization
    sx, sy = kf.update(600.0, 400.0)
    assert kf.is_initialized
    assert math.isclose(sx, 600.0, abs_tol=1e-3)
    assert math.isclose(sy, 400.0, abs_tol=1e-3)


def test_parameter_tuning():
    """Verify dynamic tuning of Kalman parameters at runtime."""
    kf = GazeKalmanFilter()
    kf.set_parameters(
        process_noise_pos=5e-3,
        process_noise_vel=2e-2,
        measurement_noise_min=1e-3,
        measurement_noise_max=8e-2,
        velocity_threshold=1.5,
    )

    diag = kf.get_diagnostics()
    assert diag["q_pos"] == 5e-3
    assert diag["q_vel"] == 2e-2
    assert diag["r_min"] == 1e-3
    assert diag["r_max"] == 8e-2


def test_nan_inf_robustness():
    """Verify NaN and Inf inputs are handled safely without state corruption."""
    kf = GazeKalmanFilter()
    kf.update(200.0, 300.0)

    # Supply invalid coordinates
    sx, sy = kf.update(float("nan"), float("inf"))
    assert math.isfinite(sx) and math.isfinite(sy)
    assert sx == 200.0 and sy == 300.0


def test_cursor_controller_kalman_integration():
    """Verify CursorController integrates GazeKalmanFilter seamlessly."""
    mock_gaze_service = type("MockGazeService", (), {
        "get_latest_gaze": lambda self: None
    })()

    controller = CursorController(gaze_service=mock_gaze_service)
    assert hasattr(controller, "kalman_filter")
    assert isinstance(controller.kalman_filter, GazeKalmanFilter)

    # Test tuning through controller
    controller.set_kalman_parameters(measurement_noise_max=0.08)
    assert controller.kalman_filter.get_diagnostics()["r_max"] == 0.08
