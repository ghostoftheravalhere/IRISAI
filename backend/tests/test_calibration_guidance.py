"""Unit tests for Calibration Guidance Engine (Posture, Distance, Centering & Head Pose)."""

from __future__ import annotations

import pytest

from backend.eye_tracking.calibration_guidance import CalibrationGuidanceService
from backend.eye_tracking.face_mesh_service import EyeData, NormalizedLandmark


def make_eye_data(
    left_x: float = 0.40,
    left_y: float = 0.50,
    left_z: float = 0.0,
    right_x: float = 0.60,
    right_y: float = 0.50,
    right_z: float = 0.0,
) -> EyeData:
    left_eye = tuple(NormalizedLandmark(index=i, x=left_x, y=left_y, z=left_z) for i in range(16))
    right_eye = tuple(NormalizedLandmark(index=i, x=right_x, y=right_y, z=right_z) for i in range(16))
    return EyeData(left_eye=left_eye, right_eye=right_eye)


# Condition 1: Centered / Good Posture
def test_guidance_good_posture():
    svc = CalibrationGuidanceService(stabilization_window_seconds=0.0)
    eye_data = make_eye_data(left_x=0.40, right_x=0.60, left_y=0.50, right_y=0.50)
    st = svc.evaluate_posture(eye_data)

    assert st.status == "good"
    assert "Good position" in st.message
    assert st.is_stable is True


# Condition 2: Face Too Far (inter-eye distance < 0.16)
def test_guidance_face_too_far():
    svc = CalibrationGuidanceService()
    eye_data = make_eye_data(left_x=0.45, right_x=0.50)  # dist = 0.05
    st = svc.evaluate_posture(eye_data)

    assert st.status == "face_too_far"
    assert "Move closer" in st.message
    assert st.is_stable is False


# Condition 3: Face Too Close (inter-eye distance > 0.38)
def test_guidance_face_too_close():
    svc = CalibrationGuidanceService()
    eye_data = make_eye_data(left_x=0.20, right_x=0.70)  # dist = 0.50
    st = svc.evaluate_posture(eye_data)

    assert st.status == "face_too_close"
    assert "Move farther away" in st.message
    assert st.is_stable is False


# Condition 4: Face Off-Center Left (midpoint_x < 0.35)
def test_guidance_face_too_left():
    svc = CalibrationGuidanceService()
    eye_data = make_eye_data(left_x=0.15, right_x=0.35)  # mid_x = 0.25
    st = svc.evaluate_posture(eye_data)

    assert st.status == "face_too_left"
    assert "Move right" in st.message


# Condition 5: Face Off-Center Right (midpoint_x > 0.65)
def test_guidance_face_too_right():
    svc = CalibrationGuidanceService()
    eye_data = make_eye_data(left_x=0.65, right_x=0.85)  # mid_x = 0.75
    st = svc.evaluate_posture(eye_data)

    assert st.status == "face_too_right"
    assert "Move left" in st.message


# Condition 6: Face Off-Center High (midpoint_y < 0.30)
def test_guidance_face_too_high():
    svc = CalibrationGuidanceService()
    eye_data = make_eye_data(left_x=0.40, right_x=0.60, left_y=0.20, right_y=0.20)
    st = svc.evaluate_posture(eye_data)

    assert st.status == "face_too_high"
    assert "Lower your face" in st.message


# Condition 7: Face Off-Center Low (midpoint_y > 0.70)
def test_guidance_face_too_low():
    svc = CalibrationGuidanceService()
    eye_data = make_eye_data(left_x=0.40, right_x=0.60, left_y=0.80, right_y=0.80)
    st = svc.evaluate_posture(eye_data)

    assert st.status == "face_too_low"
    assert "Raise your face" in st.message


# Condition 8: Head Turned / Yaw Delta (|z_left - z_right| > 0.08)
def test_guidance_head_turned():
    svc = CalibrationGuidanceService()
    eye_data = make_eye_data(left_x=0.40, right_x=0.60, left_z=0.10, right_z=0.0)
    st = svc.evaluate_posture(eye_data)

    assert st.status == "head_turned"
    assert "Keep your head straight" in st.message


# Condition 9: Missing Face / Tracking Lost
def test_guidance_tracking_lost():
    svc = CalibrationGuidanceService()
    st = svc.evaluate_posture(None)

    assert st.status == "tracking_lost"
    assert "Face not detected" in st.message
    assert st.confidence == 0.0
