"""Vision, filtering, calibration, and head pose estimation package."""

from backend.vision.calibration_engine import (
    NINE_POINT_GRID,
    CalibrationDataPoint,
    HeadPoseAnchor,
    PolynomialCalibrator,
    PolynomialMappingResult,
)
from backend.vision.head_pose import FACE_MODEL_3D, HeadPose, HeadPoseEstimator
from backend.vision.kalman_filter import GazeKalmanFilter

__all__ = [
    "CalibrationDataPoint",
    "FACE_MODEL_3D",
    "GazeKalmanFilter",
    "HeadPose",
    "HeadPoseAnchor",
    "HeadPoseEstimator",
    "NINE_POINT_GRID",
    "PolynomialCalibrator",
    "PolynomialMappingResult",
]
