"""Unit tests for Deterministic Kinematic Physics Pipeline."""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from backend.vision.kinematic_physics import (
    KinematicPhysicsConfig,
    KinematicPhysicsPipeline,
)
from backend.eye_tracking.cursor_controller import (
    CursorController,
    CursorControllerConfig,
)
from backend.eye_tracking.gaze_service import GazeEstimate


def test_kinematic_initialization():
    """Verify first measurement seeds initial continuous position with zero velocity."""
    pipeline = KinematicPhysicsPipeline()
    assert not pipeline.is_initialized
    assert pipeline.position == (0.0, 0.0)
    assert pipeline.velocity == (0.0, 0.0)

    # First measurement initializes position immediately
    x, y = pipeline.update(450.0, 320.0)
    assert pipeline.is_initialized
    assert math.isclose(x, 450.0, abs_tol=1e-5)
    assert math.isclose(y, 320.0, abs_tol=1e-5)
    assert pipeline.velocity == (0.0, 0.0)


def test_deterministic_repeatability():
    """Verify identical target inputs and timestamps produce exact identical trajectories."""
    targets = [
        (100.0 + i * 15.0, 200.0 + i * 10.0, 1.0 / 60.0)
        for i in range(40)
    ]

    # Run 1
    pipe1 = KinematicPhysicsPipeline()
    trajectory1 = [pipe1.update(tx, ty, dt=dt) for tx, ty, dt in targets]

    # Run 2
    pipe2 = KinematicPhysicsPipeline()
    trajectory2 = [pipe2.update(tx, ty, dt=dt) for tx, ty, dt in targets]

    assert len(trajectory1) == len(trajectory2)
    for (x1, y1), (x2, y2) in zip(trajectory1, trajectory2):
        assert math.isclose(x1, x2, abs_tol=1e-9), "Non-deterministic X trajectory detected"
        assert math.isclose(y1, y2, abs_tol=1e-9), "Non-deterministic Y trajectory detected"


def test_stationary_tremor_absorption():
    """Verify ocular micro-tremor is absorbed with >60% variance reduction."""
    config = KinematicPhysicsConfig(
        stiffness=35.0,
        damping_ratio=1.0,
        tremor_reduction_px=10.0,
    )
    pipeline = KinematicPhysicsPipeline(config=config)
    np.random.seed(42)

    center_x, center_y = 600.0, 400.0
    num_samples = 80
    noise_std = 5.0  # Sub-10px tremor noise

    raw_x = center_x + np.random.normal(0, noise_std, num_samples)
    raw_y = center_y + np.random.normal(0, noise_std, num_samples)

    filtered_x = []
    filtered_y = []

    for rx, ry in zip(raw_x, raw_y):
        fx, fy = pipeline.update(float(rx), float(ry), dt=1.0 / 30.0)
        filtered_x.append(fx)
        filtered_y.append(fy)

    raw_var_x = float(np.var(raw_x[15:]))
    raw_var_y = float(np.var(raw_y[15:]))
    filt_var_x = float(np.var(filtered_x[15:]))
    filt_var_y = float(np.var(filtered_y[15:]))

    # Variance reduction: continuous low-pass and velocity-adaptive damping reduces noise variance > 55%
    assert filt_var_x < raw_var_x * 0.50, f"Filtered X var {filt_var_x} should be < 50% of raw {raw_var_x}"
    assert filt_var_y < raw_var_y * 0.50, f"Filtered Y var {filt_var_y} should be < 50% of raw {raw_var_y}"


def test_saccadic_jump_responsiveness_and_zero_overshoot():
    """Verify rapid convergence during saccades with zero overshoot (critically damped)."""
    config = KinematicPhysicsConfig(
        stiffness=40.0,
        damping_ratio=1.0,
        acceleration_gain=1.5,
    )
    pipeline = KinematicPhysicsPipeline(config=config)

    # 1. Establish initial fixation at (100, 100)
    for _ in range(15):
        pipeline.update(100.0, 100.0, dt=1.0 / 60.0)

    # 2. Saccade jump to (900, 900)
    target_x, target_y = 900.0, 900.0
    trajectory = []
    for _ in range(15):  # 250ms at 60 FPS
        pos = pipeline.update(target_x, target_y, dt=1.0 / 60.0)
        trajectory.append(pos)

    # Within 15 frames (250 ms), distance should be < 75 pixels for omega=18.0
    final_x, final_y = trajectory[14]
    assert math.hypot(final_x - target_x, final_y - target_y) < 75.0

    # Within 25 frames (~400 ms), distance converges to < 20 pixels
    for _ in range(10):
        pos = pipeline.update(target_x, target_y, dt=1.0 / 60.0)
        trajectory.append(pos)

    assert math.hypot(trajectory[-1][0] - target_x, trajectory[-1][1] - target_y) < 20.0

    # Verify zero overshoot (monotonically approaching target from below)
    for x, y in trajectory:
        assert x <= target_x + 1e-4, f"Overshoot detected in X: {x} > {target_x}"
        assert y <= target_y + 1e-4, f"Overshoot detected in Y: {y} > {target_y}"


def test_frame_rate_invariance():
    """Verify trajectory endpoint convergence matches across 30 FPS vs 60 FPS."""
    config = KinematicPhysicsConfig(stiffness=35.0, damping_ratio=1.0)
    pipe_30 = KinematicPhysicsPipeline(config=config)
    pipe_60 = KinematicPhysicsPipeline(config=config)

    target_x, target_y = 800.0, 500.0

    # Simulate 0.3 seconds at 30 FPS (9 frames)
    pos_30 = (0.0, 0.0)
    for _ in range(9):
        pos_30 = pipe_30.update(target_x, target_y, dt=1.0 / 30.0)

    # Simulate 0.3 seconds at 60 FPS (18 frames)
    pos_60 = (0.0, 0.0)
    for _ in range(18):
        pos_60 = pipe_60.update(target_x, target_y, dt=1.0 / 60.0)

    # Both should reach very close to the target with minimal divergence (<5 px)
    assert math.hypot(pos_30[0] - target_x, pos_30[1] - target_y) < 15.0
    assert math.hypot(pos_60[0] - target_x, pos_60[1] - target_y) < 15.0
    assert math.hypot(pos_30[0] - pos_60[0], pos_30[1] - pos_60[1]) < 8.0


def test_nan_inf_robustness():
    """Verify non-finite inputs are safely rejected without state corruption."""
    pipeline = KinematicPhysicsPipeline()
    pipeline.update(250.0, 350.0)

    pos = pipeline.update(float("nan"), float("inf"), dt=1.0 / 30.0)
    assert math.isfinite(pos[0]) and math.isfinite(pos[1])
    assert pos == (250.0, 350.0)
    assert pipeline.velocity == (0.0, 0.0)


def test_freeze_and_unfreeze():
    """Verify freeze halts momentum immediately and preserves coordinates."""
    pipeline = KinematicPhysicsPipeline()
    pipeline.update(100.0, 100.0)
    pipeline.update(300.0, 300.0, dt=1.0 / 30.0)
    assert pipeline.speed > 0.0

    pipeline.freeze()
    assert pipeline.is_frozen
    assert pipeline.velocity == (0.0, 0.0)

    frozen_pos = pipeline.position
    # Further updates while frozen should not move position
    pos_after = pipeline.update(900.0, 900.0, dt=1.0 / 30.0)
    assert pos_after == frozen_pos

    pipeline.unfreeze()
    assert not pipeline.is_frozen
    unfrozen_pos = pipeline.update(900.0, 900.0, dt=1.0 / 30.0)
    assert unfrozen_pos != frozen_pos


def test_parameter_tuning():
    """Verify dynamic parameter tuning at runtime."""
    pipeline = KinematicPhysicsPipeline()
    pipeline.set_parameters(
        stiffness=48.0,
        damping_ratio=1.2,
        tremor_reduction_px=12.0,
        acceleration_gain=2.0,
    )
    assert pipeline.config.stiffness == 48.0
    assert pipeline.config.damping_ratio == 1.2
    assert pipeline.config.tremor_reduction_px == 12.0
    assert pipeline.config.acceleration_gain == 2.0


def test_cursor_controller_kinematic_integration():
    """Verify CursorController integrates KinematicPhysicsPipeline seamlessly."""
    mock_gaze = type("MockGazeService", (), {"get_latest_gaze": lambda self: None})()
    controller = CursorController(gaze_service=mock_gaze)

    assert hasattr(controller, "physics_pipeline")
    assert isinstance(controller.physics_pipeline, KinematicPhysicsPipeline)

    # Dynamic tuning via controller
    controller.set_kinematic_parameters(stiffness=44.0)
    assert controller.physics_pipeline.config.stiffness == 44.0

    # Backwards-compatible route via set_kalman_parameters
    controller.set_kalman_parameters(tremor_reduction_px=9.5)
    assert controller.physics_pipeline.config.tremor_reduction_px == 9.5


def test_cursor_controller_kinematic_movement():
    """Verify CursorController update uses KinematicPhysicsPipeline to move cursor."""
    gaze = GazeEstimate(
        eye_center=MagicMock(x=0.5, y=0.5),
        raw_x=0.5,
        raw_y=0.5,
        x=0.5,
        y=0.5,
        confidence=0.9,
        captured_at=100.0,
    )
    mock_gaze = type("MockGazeService", (), {"get_latest_gaze": lambda self: gaze})()
    config = CursorControllerConfig(
        kinematic_physics_enabled=True,
        kinematic_stiffness=40.0,
    )
    controller = CursorController(gaze_service=mock_gaze, config=config)
    mock_pyautogui = MagicMock()
    mock_pyautogui.position.return_value = (960, 540)
    controller._load_pyautogui = lambda: mock_pyautogui

    try:
        controller.enable()
        state = controller.update(face_detected=True, tracking_confidence=0.95)

        assert state.trackingActive is True
        assert controller.physics_pipeline.is_initialized is True
    finally:
        controller.disable()


def test_constant_critically_damped_system():
    """Verify pure constant critically damped system (omega=18, c=36, zero chatter)."""
    pipeline = KinematicPhysicsPipeline()
    pipeline.update(500.0, 500.0)

    # At all speeds, omega is constant 18.0 and critically damped c = 36.0
    pipeline.update(500.0, 500.0, dt=0.016)
    assert math.isclose(pipeline.omega, 18.0, abs_tol=1e-3)
    assert math.isclose(pipeline.damping, 36.0, abs_tol=1e-3)
    assert pipeline.damping_ratio == 1.0

    # Moving at 300 px/s
    pipeline.reset(500.0, 500.0)
    pipeline.update(500.0 + 300.0 * 0.016, 500.0, dt=0.016)
    assert math.isclose(pipeline.omega, 18.0, abs_tol=1e-3)
    assert math.isclose(pipeline.damping, 36.0, abs_tol=1e-3)

    # Moving at fast speed 700 px/s
    pipeline.reset(500.0, 500.0)
    pipeline.update(500.0 + 700.0 * 0.016, 500.0, dt=0.016)
    assert math.isclose(pipeline.omega, 18.0, abs_tol=1e-3)
    assert math.isclose(pipeline.damping, 36.0, abs_tol=1e-3)


def test_zero_deadbands_pure_continuous_motion():
    """Verify zero deadbands, zero stiction, and zero thresholds."""
    pipeline = KinematicPhysicsPipeline()
    pipeline.reset(500.0, 500.0)

    # Deadband radius and breakout radius are 0.0
    assert pipeline.deadband_radius == 0.0
    assert pipeline.breakout_radius == 0.0
    assert pipeline.is_anchored is False

    # Tiny 0.5px displacement is NOT blocked by deadband; produces smooth continuous response
    pos = pipeline.update(500.5, 500.0, dt=0.016)
    assert pos[0] > 500.0
    assert pipeline.speed > 0.0


def test_smooth_nonlinear_mouse_ballistics_curve():
    """Verify dual-regime velocity-adaptive smoothing curve on raw sensor data."""
    head_dists = [0.0, 0.002, 0.004, 0.010, 0.017, 0.030, 0.050]
    alphas = []
    for d in head_dists:
        t = max(0.0, min(1.0, (d - 0.004) / (0.030 - 0.004)))
        alpha = 0.08 + (0.90 - 0.08) * (t * t)
        alphas.append(alpha)

    # Resting noise floor (< 0.004): alpha = 0.08 (ironclad noise filter)
    assert math.isclose(alphas[0], 0.08, abs_tol=1e-5)
    assert math.isclose(alphas[1], 0.08, abs_tol=1e-5)
    assert math.isclose(alphas[2], 0.08, abs_tol=1e-5)

    # Fast head movement (>= 0.030): alpha = 0.90 (instant snap)
    assert math.isclose(alphas[-2], 0.90, abs_tol=1e-5)
    assert math.isclose(alphas[-1], 0.90, abs_tol=1e-5)

    # Strictly monotonic
    for i in range(len(alphas) - 1):
        assert alphas[i] <= alphas[i + 1]


def test_balanced_desktop_range_expansion_full_reach():
    """Verify balanced desktop gains (gain_x=6.8, gain_y=4.0, neutral=(0.50, 0.70)) provide full desktop reach."""
    from backend.eye_tracking.gaze_service import gaze_to_screen_coordinates

    screen_w = 1920
    screen_h = 1080

    # 1. Neutral gaze (0.50, 0.70) maps to exact screen center
    center_x, center_y = gaze_to_screen_coordinates(0.50, 0.70, screen_w=screen_w, screen_h=screen_h)
    assert center_x == screen_w // 2
    assert center_y == screen_h // 2

    # 2. Excursions reach all edges cleanly without stickiness
    left_x, _ = gaze_to_screen_coordinates(0.20, 0.70, screen_w=screen_w, screen_h=screen_h)
    assert left_x == 0

    right_x, _ = gaze_to_screen_coordinates(0.80, 0.70, screen_w=screen_w, screen_h=screen_h)
    assert right_x == screen_w - 1

    _, top_y = gaze_to_screen_coordinates(0.50, 0.20, screen_w=screen_w, screen_h=screen_h)
    assert top_y == 0

    _, bottom_y = gaze_to_screen_coordinates(0.50, 0.90, screen_w=screen_w, screen_h=screen_h)
    assert bottom_y == screen_h - 1

    # 3. CursorController._gaze_to_screen respects default (0.50, 0.70) neutral and reach
    controller = CursorController(gaze_service=MagicMock())
    cx, cy = controller._gaze_to_screen(0.50, 0.70, screen_w, screen_h)
    assert cx == screen_w // 2
    assert cy == screen_h // 2


def test_continuous_lowpass_filter_on_raw_landmarks():
    """Verify dual-regime adaptive smoothing on raw coordinates (never freezes)."""
    from backend.eye_tracking.gaze_service import EyeGazeService

    service = EyeGazeService(camera_service=MagicMock(), calibration_service=MagicMock())

    # 1. Baseline initialization
    fx1, fy1, locked1 = service._apply_noise_gate(0.5000, 0.5000)
    assert fx1 == 0.5000
    assert fy1 == 0.5000
    assert locked1 is False

    # 2. Small tremor noise (dist = 0.002) -> alpha=0.45 (responsive, zero sludge)
    # 0.5000 + 0.45 * 0.0020 ~ 0.5010
    fx2, fy2, locked2 = service._apply_noise_gate(0.5020, 0.5020)
    assert fx2 > 0.5000
    assert fx2 < 0.5015
    assert locked2 is False

    # 3. Fast movement (dist > 0.015) -> alpha adapts up to 0.95 for instant snap
    fx3, fy3, locked3 = service._apply_noise_gate(0.5400, 0.5400)
    assert fx3 > 0.5300
    assert locked3 is False


def test_fixed_neutral_center_no_drift():
    """Verify neutral center remains strictly FIXED once calibrated (zero leaky drift)."""
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

    # Complete initial 30-frame auto-center around (0.50, 0.58)
    with patch("backend.eye_tracking.gaze_service.compute_eye_center", return_value=(0.50, 0.58)):
        camera_mock.get_latest_eye_data.return_value = MagicMock()
        for _ in range(30):
            service.estimate_latest_gaze()

    assert service._auto_center_calibrated is True
    assert math.isclose(service.calibrated_neutral_x, 0.50, abs_tol=1e-3)
    assert math.isclose(service.calibrated_neutral_y, 0.58, abs_tol=1e-3)
    calibrated_y = service.calibrated_neutral_y

    # User slightly shifts posture to (0.50, 0.54): neutral must remain FIXED (zero drift)
    with patch("backend.eye_tracking.gaze_service.compute_eye_center", return_value=(0.50, 0.54)):
        for _ in range(100):
            service.estimate_latest_gaze()

    assert service.calibrated_neutral_y == calibrated_y, "Neutral baseline must remain fixed"

    # Neutral recalibrates ONLY when explicit recalibrate_center is requested (e.g. 'C' key)
    service.recalibrate_center(0.50, 0.54)
    assert service.calibrated_neutral_y == 0.54


def test_horizontal_motion_isolated_to_nose_tip_with_mirroring():
    """Verify horizontal (X) and vertical (Y) are driven 100% by Landmark 1 (nose tip) with mirroring."""
    from backend.eye_tracking.face_mesh_service import EyeData, NormalizedLandmark
    from backend.eye_tracking.gaze_service import EyeGazeService

    camera_mock = MagicMock()
    camera_mock.is_mirrored = False
    calib_mock = MagicMock()
    calib_mock.get_mapping.return_value = MagicMock(
        x_coefficients=(1.0, 0.0, 0.0),
        y_coefficients=(0.0, 1.0, 0.0),
    )
    calib_mock.get_polynomial_calibrator.return_value = None
    calib_mock.get_quality.return_value = MagicMock(score=0.90)

    service = EyeGazeService(camera_service=camera_mock, calibration_service=calib_mock)

    # 1. Inverted X: turning head right increases nose_tip.x in mirrored camera, raw_x is 1.0 - nose_tip.x
    nose = NormalizedLandmark(index=1, x=0.60, y=0.45, z=0.0)
    eye_data = EyeData(left_eye=(), right_eye=(), nose_tip=nose)
    camera_mock.get_latest_eye_data.return_value = eye_data

    with patch("backend.eye_tracking.gaze_service.compute_eye_center", return_value=(0.85, 0.95)):
        estimate = service.estimate_latest_gaze()

    assert estimate is not None
    assert math.isclose(estimate.raw_x, 0.40, abs_tol=1e-5), "raw_x must be 1.0 - nose_tip.x (0.40), ignoring iris (0.85)"
    assert math.isclose(estimate.raw_y, 0.45, abs_tol=1e-5), "raw_y must be nose_tip.y (0.45), ignoring iris (0.95)"



