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
