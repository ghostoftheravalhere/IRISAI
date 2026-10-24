"""Tests for eye calibration and cursor enable/disable API endpoints."""

import time
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.eye_tracking.calibration import (
    CalibrationMapping,
    CalibrationQuality,
    CalibrationSample,
    EyeCenter,
)
from backend.eye_tracking.face_mesh_service import EyeData, NormalizedLandmark


def test_cursor_enable_blocked_before_calibration():
    app = create_app()
    client = TestClient(app)

    response = client.post("/eye/cursor/enable")
    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert "detail" in data
    assert "Calibration must be complete" in data["detail"]


def test_cursor_enable_blocked_low_quality_calibration():
    app = create_app()
    client = TestClient(app)

    calib = app.state.eye_calibration
    low_quality = CalibrationQuality(
        score=0.30, rmse=0.45, label="POOR", recommend_recalibration=True
    )
    mock_mapping = CalibrationMapping(
        x_coefficients=(1.5, 0.0, -0.2),
        y_coefficients=(0.0, 1.5, -0.2),
        sample_count=9,
        quality=low_quality,
    )
    calib._mapping = mock_mapping
    calib._quality = low_quality
    calib._samples = [
        CalibrationSample(
            point=pt,
            eye_data=EyeData(
                left_eye=tuple(NormalizedLandmark(index=i, x=0.5, y=0.5, z=0.0) for i in range(16)),
                right_eye=tuple(NormalizedLandmark(index=i, x=0.5, y=0.5, z=0.0) for i in range(16)),
            ),
            eye_center=EyeCenter(x=0.5, y=0.5),
            captured_at=time.time(),
        )
        for pt in calib.points
    ]
    calib._saved_state = calib.save_state()

    response = client.post("/eye/cursor/enable")
    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert "detail" in data
    assert "Calibration quality is too low" in data["detail"]


def test_cursor_enable_and_disable_success():
    app = create_app()
    client = TestClient(app)

    calib = app.state.eye_calibration
    good_quality = CalibrationQuality(
        score=0.95, rmse=0.01, label="EXCELLENT", recommend_recalibration=False
    )
    mock_mapping = CalibrationMapping(
        x_coefficients=(1.5, 0.0, -0.2),
        y_coefficients=(0.0, 1.5, -0.2),
        sample_count=9,
        quality=good_quality,
    )
    calib._mapping = mock_mapping
    calib._quality = good_quality
    calib._samples = [
        CalibrationSample(
            point=pt,
            eye_data=EyeData(
                left_eye=tuple(NormalizedLandmark(index=i, x=0.5, y=0.5, z=0.0) for i in range(16)),
                right_eye=tuple(NormalizedLandmark(index=i, x=0.5, y=0.5, z=0.0) for i in range(16)),
            ),
            eye_center=EyeCenter(x=0.5, y=0.5),
            captured_at=time.time(),
        )
        for pt in calib.points
    ]
    calib._saved_state = calib.save_state()

    # Initial state
    assert app.state.cursor_controller.get_state().enabled is False

    # POST /eye/cursor/enable
    response = client.post("/eye/cursor/enable")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert data["enabled"] is True
    assert "dragMode" in data
    assert "trackingActive" in data
    assert "trackingConfidence" in data
    assert app.state.cursor_controller.get_state().enabled is True

    # POST /eye/cursor/disable
    resp_disable = client.post("/eye/cursor/disable")
    assert resp_disable.status_code == 200
    data_dis = resp_disable.json()
    assert data_dis["enabled"] is False
    assert app.state.cursor_controller.get_state().enabled is False


def test_recalibrate_center_api_endpoint():
    app = create_app()
    client = TestClient(app)

    # POST /api/eye/recalibrate-center
    resp = client.post("/api/eye/recalibrate-center", json={"neutral_x": 0.49, "neutral_y": 0.58})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "recalibrated"
    assert data["neutral_x"] == 0.49
    assert data["neutral_y"] == 0.58

    # POST /eye/recalibrate-center without body (triggers dynamic auto-recalibration)
    resp2 = client.post("/eye/recalibrate-center")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "recalibrated"
    assert "neutral_x" in data2
    assert "neutral_y" in data2


def test_cursor_enable_blocked_if_validation_failed():
    """Verify POST /eye/cursor/enable is rejected with 409 when validation report fails gates."""
    from backend.eye_tracking.calibration import ValidationReport

    app = create_app()
    client = TestClient(app)

    calib = app.state.eye_calibration
    good_quality = CalibrationQuality(
        score=0.95, rmse=0.01, label="EXCELLENT", recommend_recalibration=False
    )
    mock_mapping = CalibrationMapping(
        x_coefficients=(1.5, 0.0, -0.2),
        y_coefficients=(0.0, 1.5, -0.2),
        sample_count=16,
        quality=good_quality,
    )
    calib._mapping = mock_mapping
    calib._quality = good_quality
    calib._complete = True
    calib._samples = [
        CalibrationSample(
            point=pt,
            eye_data=EyeData(
                left_eye=tuple(NormalizedLandmark(index=i, x=0.5, y=0.5, z=0.0) for i in range(16)),
                right_eye=tuple(NormalizedLandmark(index=i, x=0.5, y=0.5, z=0.0) for i in range(16)),
            ),
            eye_center=EyeCenter(x=0.5, y=0.5),
            captured_at=time.time(),
        )
        for pt in calib.training_points
    ]
    # Validation failed report (mean error exceeds 0.08 gate)
    calib._validation_report = ValidationReport(
        mean_norm_error=0.125,
        max_norm_error=0.220,
        per_target_norm_errors=(0.10, 0.12, 0.13, 0.15),
        passed=False,
    )
    calib._is_calibrated = False

    resp = client.post("/eye/cursor/enable")
    assert resp.status_code == 409
    assert "validation gates failed" in resp.json()["detail"].lower() or "not authorized" in resp.json()["detail"].lower()


def test_cursor_revocation_on_restart():
    """Verify calibration restart revokes authorization and blocks cursor activation."""
    app = create_app()
    client = TestClient(app)

    calib = app.state.eye_calibration
    good_quality = CalibrationQuality(
        score=0.95, rmse=0.01, label="EXCELLENT", recommend_recalibration=False
    )
    mock_mapping = CalibrationMapping(
        x_coefficients=(1.5, 0.0, -0.2),
        y_coefficients=(0.0, 1.5, -0.2),
        sample_count=9,
        quality=good_quality,
    )
    calib._mapping = mock_mapping
    calib._quality = good_quality
    calib._samples = [
        CalibrationSample(
            point=pt,
            eye_data=EyeData(
                left_eye=tuple(NormalizedLandmark(index=i, x=0.5, y=0.5, z=0.0) for i in range(16)),
                right_eye=tuple(NormalizedLandmark(index=i, x=0.5, y=0.5, z=0.0) for i in range(16)),
            ),
            eye_center=EyeCenter(x=0.5, y=0.5),
            captured_at=time.time(),
        )
        for pt in calib.points
    ]
    calib._saved_state = calib.save_state()

    # Enable succeeds
    enable_resp = client.post("/eye/cursor/enable")
    assert enable_resp.status_code == 200
    assert app.state.cursor_controller.get_state().enabled is True

    # Restart calibration -> revokes authorization and disables cursor
    restart_resp = client.post("/eye/calibration/restart")
    assert restart_resp.status_code == 200
    assert app.state.cursor_controller.get_state().enabled is False
    assert calib.is_calibrated is False

    # Stale reactivation attempt must fail with 409
    re_enable_resp = client.post("/eye/cursor/enable")
    assert re_enable_resp.status_code == 409


def test_cursor_controller_auto_disables_on_revocation():
    """Verify cursor controller automatically disables after 3 frames if authorization is revoked."""
    from unittest.mock import MagicMock
    from backend.eye_tracking.cursor_controller import CursorController, CursorControllerConfig

    mock_auth = MagicMock()
    mock_auth.is_calibrated = True

    mock_gaze = MagicMock()
    mock_gaze.get_latest_gaze.return_value = None
    ctrl = CursorController(gaze_service=mock_gaze, auth_service=mock_auth)
    mock_pyautogui = MagicMock()
    mock_pyautogui.position.return_value = (500, 500)
    ctrl._load_pyautogui = lambda: mock_pyautogui

    # Enable with valid auth
    state = ctrl.enable()
    assert state.enabled is True

    # Revoke authorization
    mock_auth.is_calibrated = False

    # Feed updates: after 3 frames, should automatically disable
    ctrl.update()
    assert ctrl.get_state().enabled is True
    assert ctrl._unauthorized_consecutive_frames == 1

    ctrl.update()
    assert ctrl.get_state().enabled is True
    assert ctrl._unauthorized_consecutive_frames == 2

    ctrl.update()
    assert ctrl.get_state().enabled is False
    assert ctrl._tracking_active is False


def test_calibration_restart_mode_selection():
    """Verify restarting calibration allows switching between 9-point and 16-point modes."""
    app = create_app()
    client = TestClient(app)

    # 1. Restart with 9-point mode
    r9 = client.post("/eye/calibration/restart", json={"mode": "9-point"})
    assert r9.status_code == 200
    data9 = r9.json()
    assert data9["total_points"] == 9
    assert app.state.eye_calibration.mode == "9-point"
    assert len(app.state.eye_calibration.training_points) == 9
    assert len(app.state.eye_calibration.validation_points) == 0

    # 2. Restart with 16-point mode
    r16 = client.post("/eye/calibration/restart", json={"mode": "16-point"})
    assert r16.status_code == 200
    data16 = r16.json()
    assert data16["total_points"] == 20
    assert app.state.eye_calibration.mode == "16-point"
    assert len(app.state.eye_calibration.training_points) == 16
    assert len(app.state.eye_calibration.validation_points) == 4


def test_camera_service_frame_recency_and_stale_data_expiry():
    """Verify CameraService invalidates stale eye landmarks and reports capture stall."""
    from backend.eye_tracking.camera_service import CameraService
    from backend.eye_tracking.face_mesh_service import EyeData, NormalizedLandmark

    cam = CameraService()
    dummy_eye = EyeData(
        left_eye=tuple(NormalizedLandmark(index=i, x=0.5, y=0.5, z=0.0) for i in range(16)),
        right_eye=tuple(NormalizedLandmark(index=i, x=0.5, y=0.5, z=0.0) for i in range(16)),
    )
    cam._latest_eye_data = dummy_eye
    cam._has_received_frames = True

    # Simulate recent frame -> returns eye data
    import time
    import unittest.mock
    cam._last_frame_time = time.monotonic()
    # Mock is_running property
    with unittest.mock.patch.object(CameraService, "is_running", new_callable=unittest.mock.PropertyMock, return_value=True):
        assert cam.get_latest_eye_data() is dummy_eye
        assert cam.status()["running"] is True

        # Simulate frame stall > 2.5 seconds -> eye data expires and status becomes running=False
        cam._last_frame_time = time.monotonic() - 3.0
        assert cam.get_latest_eye_data() is None
        assert cam.status()["running"] is False


def test_transition_from_completed_9point_to_16point_calibration():
    """Verify restarting in 16-point mode after a completed 9-point calibration correctly resets state."""
    app = create_app()
    client = TestClient(app)

    # 1. Start and complete 9-point calibration
    r9 = client.post("/eye/calibration/restart", json={"mode": "9-point"})
    assert r9.status_code == 200
    calib = app.state.eye_calibration
    assert calib.mode == "9-point"
    assert len(calib.training_points) == 9

    from backend.eye_tracking.calibration import (
        CalibrationMapping,
        CalibrationQuality,
        CalibrationSample,
        EyeCenter,
    )
    from backend.eye_tracking.face_mesh_service import EyeData, NormalizedLandmark

    dummy_eye = EyeData(
        left_eye=tuple(NormalizedLandmark(index=i, x=0.5, y=0.5, z=0.0) for i in range(16)),
        right_eye=tuple(NormalizedLandmark(index=i, x=0.5, y=0.5, z=0.0) for i in range(16)),
    )
    for pt in calib.points:
        calib._samples.append(CalibrationSample(point=pt, eye_data=dummy_eye, eye_center=EyeCenter(pt.x, pt.y), captured_at=0.0))

    calib._complete = True
    calib._quality = CalibrationQuality(score=0.85, rmse=0.034, label="Good", recommend_recalibration=False)
    calib._mapping = CalibrationMapping(
        x_coefficients=(1.0, 0.0, 0.0),
        y_coefficients=(0.0, 1.0, 0.0),
        sample_count=9,
        quality=calib._quality,
    )
    assert calib.is_calibrated is True

    # Enabling cursor works when authorized
    en = client.post("/eye/cursor/enable")
    assert en.status_code == 200
    assert app.state.cursor_controller.get_state().enabled is True

    # 2. Transition from completed 9-point to 16-point calibration
    r16 = client.post("/eye/calibration/restart", json={"mode": "16-point"})
    assert r16.status_code == 200
    data16 = r16.json()

    # Verify authorization is revoked, samples are cleared, and 16+4 targets are configured
    assert data16["completed_points"] == 0
    assert data16["total_points"] == 20
    assert data16["complete"] is False
    assert data16["is_calibrated"] is False
    assert data16["phase"] == "training"
    assert calib.mode == "16-point"
    assert len(calib.training_points) == 16
    assert len(calib.validation_points) == 4
    assert calib.is_calibrated is False
    assert app.state.cursor_controller.get_state().enabled is False

    # Stale cursor enablement attempt is rejected
    en_stale = client.post("/eye/cursor/enable")
    assert en_stale.status_code == 409


def test_calibration_restart_payload_validation():
    """Verify restart endpoint validates mode payload types and values."""
    app = create_app()
    client = TestClient(app)

    # Invalid string mode returns 400
    r_invalid = client.post("/eye/calibration/restart", json={"mode": "invalid-mode"})
    assert r_invalid.status_code == 400
    assert "calibration mode must be" in r_invalid.json()["detail"]

    # Non-string object mode (like React SyntheticEvent) returns 422
    r_obj = client.post("/eye/calibration/restart", json={"mode": {"isTrusted": True}})
    assert r_obj.status_code == 422


def test_calibration_start_endpoint_alias():
    """Verify POST /eye/calibration/start is mounted and accepts mode parameter."""
    app = create_app()
    client = TestClient(app)

    res = client.post("/eye/calibration/start", json={"mode": "16-point"})
    assert res.status_code == 200
    data = res.json()
    assert data["total_points"] == 20
    assert data["completed_points"] == 0
    assert data["mode"] == "16-point"
    assert data["phase"] == "training"


def test_sixteen_point_validation_failure_and_restart_lifecycle():
    """Verify 16-point training transitions to validation, failure blocks cursor, and restart resets cleanly."""
    from backend.eye_tracking.calibration import (
        CalibrationSample,
        EyeCenter,
        ValidationReport,
    )
    from backend.eye_tracking.face_mesh_service import EyeData, NormalizedLandmark

    app = create_app()
    client = TestClient(app)

    # 1. Fresh 16-point session
    res_start = client.post("/eye/calibration/start", json={"mode": "16-point"})
    assert res_start.status_code == 200
    calib = app.state.eye_calibration
    assert calib.mode == "16-point"
    assert len(calib.training_points) == 16
    assert len(calib.validation_points) == 4

    dummy_eye = EyeData(
        left_eye=tuple(NormalizedLandmark(index=i, x=0.5, y=0.5, z=0.0) for i in range(16)),
        right_eye=tuple(NormalizedLandmark(index=i, x=0.5, y=0.5, z=0.0) for i in range(16)),
    )

    # 2. Simulate 16 training samples
    for pt in calib.training_points:
        calib._samples.append(
            CalibrationSample(point=pt, eye_data=dummy_eye, eye_center=EyeCenter(pt.x, pt.y), captured_at=0.0)
        )
    calib._phase = "validation"

    # Check progress at transition point
    prog_trans = calib.get_progress()
    assert prog_trans.completed_points == 16
    assert prog_trans.total_points == 20
    assert prog_trans.phase == "validation"
    assert prog_trans.current_point.index == 16  # First validation target (V1)
    assert prog_trans.complete is False
    assert prog_trans.is_calibrated is False

    # 3. Simulate 4 validation samples with high error (failing validation)
    for pt in calib.validation_points:
        calib._validation_samples.append(
            CalibrationSample(point=pt, eye_data=dummy_eye, eye_center=EyeCenter(pt.x, pt.y), captured_at=0.0)
        )
    calib._validation_sample_counts = [10, 10, 10, 10]
    calib._validation_report = ValidationReport(
        mean_norm_error=0.1250,  # Fails: > 0.0800
        max_norm_error=0.2100,   # Fails: > 0.1500
        per_target_norm_errors=(0.07, 0.11, 0.21, 0.11),
        passed=False,
    )
    calib._phase = "failed"
    calib._complete = False
    calib._is_calibrated = False

    prog_failed = calib.get_progress()
    assert prog_failed.completed_points == 20
    assert prog_failed.complete is False
    assert prog_failed.is_calibrated is False
    assert prog_failed.phase == "failed"
    assert prog_failed.validation_report.passed is False

    # Cursor enablement MUST be blocked
    res_cursor = client.post("/eye/cursor/enable")
    assert res_cursor.status_code == 409
    assert "Calibration must be complete" in res_cursor.json()["detail"] or "validation gates failed" in res_cursor.json()["detail"]

    # 4. Restart after failure resets to clean 16-point session
    res_restart = client.post("/eye/calibration/restart", json={"mode": "16-point"})
    assert res_restart.status_code == 200
    prog_restarted = res_restart.json()
    assert prog_restarted["completed_points"] == 0
    assert prog_restarted["total_points"] == 20
    assert prog_restarted["phase"] == "training"
    assert prog_restarted["complete"] is False
    assert prog_restarted["is_calibrated"] is False
    assert calib.mode == "16-point"
    assert len(calib._samples) == 0
    assert len(calib._validation_samples) == 0



