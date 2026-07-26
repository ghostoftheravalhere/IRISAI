"""Eye gaze estimation from calibrated eye landmark data."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from threading import RLock
from time import time

from backend.eye_tracking.calibration import CalibrationMapping, EyeCalibrationService, EyeCenter
from backend.eye_tracking.camera_service import CameraService
from backend.eye_tracking.eye_interaction_config import (
    EyeInteractionConfig,
    default_eye_interaction_config,
)
from backend.eye_tracking.face_mesh_service import EyeData
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class GazeEstimate:
    """Latest normalized gaze estimate with tracking confidence."""

    eye_center: EyeCenter
    raw_x: float
    raw_y: float
    x: float
    y: float
    confidence: float
    captured_at: float


class EyeGazeService:
    """Estimate normalized screen gaze from eye landmarks and calibration."""

    def __init__(
        self,
        camera_service: CameraService,
        calibration_service: EyeCalibrationService,
        smoothing_alpha: float | None = None,
        eye_config: EyeInteractionConfig | None = None,
    ) -> None:
        """Create a gaze service using existing camera and calibration services."""
        shared = eye_config or default_eye_interaction_config()
        shared.validate()
        alpha = shared.gaze_smoothing_alpha if smoothing_alpha is None else smoothing_alpha
        if not 0.0 < alpha <= 1.0:
            raise ValueError("smoothing_alpha must be in the range (0.0, 1.0].")

        self._camera_service = camera_service
        self._calibration_service = calibration_service
        self._smoothing_alpha = alpha
        self._latest_gaze: GazeEstimate | None = None
        self._smoothed_x: float | None = None
        self._smoothed_y: float | None = None
        self._lock = RLock()

    def estimate_latest_gaze(self) -> GazeEstimate | None:
        """Read latest eye data and return a smoothed normalized gaze estimate."""
        eye_data = self._camera_service.get_latest_eye_data()
        if eye_data is None:
            return self._clear_latest_gaze()

        mapping = self._calibration_service.get_mapping()
        if mapping is None:
            return self._clear_latest_gaze()

        try:
            eye_center = self._compute_eye_center(eye_data)
            raw_x, raw_y = self._apply_mapping(eye_center, mapping)
        except ValueError as exc:
            logger.warning("Skipping invalid gaze estimate: %s", exc)
            return self._clear_latest_gaze()

        quality = self._calibration_service.get_quality()
        quality_score = quality.score if quality is not None else 0.0

        with self._lock:
            smoothed_x, smoothed_y = self._apply_smoothing(raw_x, raw_y)
            confidence = self._compute_confidence(
                raw_x=raw_x,
                raw_y=raw_y,
                smoothed_x=smoothed_x,
                smoothed_y=smoothed_y,
                calibration_score=quality_score,
            )
            estimate = GazeEstimate(
                eye_center=eye_center,
                raw_x=raw_x,
                raw_y=raw_y,
                x=smoothed_x,
                y=smoothed_y,
                confidence=confidence,
                captured_at=time(),
            )
            self._latest_gaze = estimate

        return estimate

    def get_latest_gaze(self) -> GazeEstimate | None:
        """Return the latest valid gaze estimate, if available."""
        with self._lock:
            return self._latest_gaze

    def reset(self) -> None:
        """Clear the latest gaze estimate and EMA state."""
        with self._lock:
            self._latest_gaze = None
            self._smoothed_x = None
            self._smoothed_y = None
            logger.info("Eye gaze estimate state reset.")

    def _clear_latest_gaze(self) -> GazeEstimate | None:
        """Clear stale gaze data after missing or invalid inputs."""
        with self._lock:
            self._latest_gaze = None
            self._smoothed_x = None
            self._smoothed_y = None
        return None

    def _compute_confidence(
        self,
        raw_x: float,
        raw_y: float,
        smoothed_x: float,
        smoothed_y: float,
        calibration_score: float,
    ) -> float:
        """Estimate tracking confidence from stability and calibration quality."""
        # Compare against clamped raw so out-of-range mappings do not invent
        # huge jitter versus the already-clamped EMA state.
        clamped_raw_x = self._clamp_normalized(raw_x)
        clamped_raw_y = self._clamp_normalized(raw_y)
        jitter = hypot(clamped_raw_x - smoothed_x, clamped_raw_y - smoothed_y)
        stability = max(0.0, 1.0 - jitter * 8.0)
        in_bounds = self._in_bounds_factor(raw_x, raw_y)
        calibration_factor = min(max(calibration_score, 0.0), 1.0)
        confidence = 0.45 * stability + 0.35 * calibration_factor + 0.20 * in_bounds
        return min(max(confidence, 0.0), 1.0)

    @staticmethod
    def _in_bounds_factor(raw_x: float, raw_y: float) -> float:
        """Softly penalize gaze mapped outside the unit screen square."""
        if 0.0 <= raw_x <= 1.0 and 0.0 <= raw_y <= 1.0:
            return 1.0

        dx = 0.0 if 0.0 <= raw_x <= 1.0 else min(abs(raw_x), abs(raw_x - 1.0))
        dy = 0.0 if 0.0 <= raw_y <= 1.0 else min(abs(raw_y), abs(raw_y - 1.0))
        overflow = hypot(dx, dy)
        return max(0.25, 1.0 - overflow * 1.5)

    def _compute_eye_center(self, eye_data: EyeData) -> EyeCenter:
        """Compute one normalized gaze center from left and right eye landmarks."""
        landmarks = eye_data.left_eye + eye_data.right_eye
        if not landmarks:
            raise ValueError("eye landmark data is empty")

        x = sum(landmark.x for landmark in landmarks) / len(landmarks)
        y = sum(landmark.y for landmark in landmarks) / len(landmarks)
        if not isfinite(x) or not isfinite(y):
            raise ValueError("eye center contains non-finite coordinates")

        return EyeCenter(x=self._clamp_normalized(x), y=self._clamp_normalized(y))

    def _apply_mapping(
        self,
        eye_center: EyeCenter,
        mapping: CalibrationMapping,
    ) -> tuple[float, float]:
        """Apply affine calibration mapping to an eye center."""
        raw_x = self._apply_coefficients(eye_center, mapping.x_coefficients)
        raw_y = self._apply_coefficients(eye_center, mapping.y_coefficients)
        if not isfinite(raw_x) or not isfinite(raw_y):
            raise ValueError("mapped gaze contains non-finite coordinates")

        return raw_x, raw_y

    def _apply_coefficients(
        self,
        eye_center: EyeCenter,
        coefficients: tuple[float, float, float],
    ) -> float:
        """Apply one affine coefficient tuple to an eye center."""
        return (
            coefficients[0] * eye_center.x
            + coefficients[1] * eye_center.y
            + coefficients[2]
        )

    def _apply_smoothing(self, x: float, y: float) -> tuple[float, float]:
        """Apply EMA smoothing to normalized gaze coordinates."""
        if self._smoothed_x is None or self._smoothed_y is None:
            self._smoothed_x = x
            self._smoothed_y = y
        else:
            alpha = self._smoothing_alpha
            self._smoothed_x = alpha * x + (1.0 - alpha) * self._smoothed_x
            self._smoothed_y = alpha * y + (1.0 - alpha) * self._smoothed_y

        return (
            self._clamp_normalized(self._smoothed_x),
            self._clamp_normalized(self._smoothed_y),
        )

    def _clamp_normalized(self, value: float) -> float:
        """Clamp a coordinate to the normalized screen range."""
        return min(max(float(value), 0.0), 1.0)
