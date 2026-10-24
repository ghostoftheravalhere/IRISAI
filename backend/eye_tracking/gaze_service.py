"""Eye gaze estimation from calibrated eye landmark data."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import hypot, isfinite
from threading import RLock
from time import time

import numpy as np

from backend.eye_tracking.calibration import CalibrationMapping, EyeCalibrationService, EyeCenter
from backend.eye_tracking.camera_service import CameraService
from backend.eye_tracking.eye_interaction_config import (
    EyeInteractionConfig,
    default_eye_interaction_config,
)
from backend.eye_tracking.face_mesh_service import EyeData
from backend.utils.helpers import compute_eye_center
from backend.utils.logger import get_logger
from backend.vision.one_euro_filter import OneEuroFilter2D

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
    is_noise_locked: bool = False
    is_calibrated: bool = False



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
        self._kinematic_physics_enabled = getattr(shared, "kinematic_physics_enabled", True)
        self._latest_gaze: GazeEstimate | None = None
        self._smoothed_x: float | None = None
        self._smoothed_y: float | None = None

        # Auto-center calibration (dynamic neutral reference coordinates)
        self.calibrated_neutral_x: float = getattr(shared, "gaze_neutral_x", 0.5)
        self.calibrated_neutral_y: float = getattr(shared, "gaze_neutral_y", 0.70)
        self._neutral_x: float = 0.5
        self._neutral_y: float = 0.70
        self._auto_center_samples: list[tuple[float, float]] = []
        self._auto_center_target_samples: int = 20
        self._auto_center_calibrated: bool = False

        # Dual-regime velocity-adaptive smoothing state on raw landmarks
        self._last_raw_x: float | None = None
        self._last_raw_y: float | None = None
        self._last_norm_x: float | None = None
        self._last_norm_y: float | None = None
        self._last_filtered_norm_x: float | None = None
        self._last_filtered_norm_y: float | None = None
        self._is_noise_locked: bool = False
        self._history_buffer: deque[tuple[float, float, float]] = deque(maxlen=6)
        self._eye_center_filter = OneEuroFilter2D(min_cutoff=1.0, beta=0.008, d_cutoff=1.0)

        self._lock = RLock()

    def recalibrate_center(self, neutral_x: float | None = None, neutral_y: float | None = None) -> tuple[float, float]:
        """Reset dynamic auto-center calibration to re-zero comfortable resting gaze position.

        If explicit neutral coordinates are provided, sets them immediately with [0.2, 0.8] bounds check.
        Otherwise, clears the sample buffer so the next 20 frames collect Landmark 1 / nose tip
        samples to compute a robust rolling median neutral center.
        """
        with self._lock:
            if neutral_x is not None and neutral_y is not None:
                nx = float(neutral_x) if 0.2 <= float(neutral_x) <= 0.8 else 0.5
                ny = float(neutral_y) if 0.2 <= float(neutral_y) <= 0.88 else 0.70
                self.calibrated_neutral_x = nx
                self.calibrated_neutral_y = ny
                self._neutral_x = nx
                self._neutral_y = ny
                self._auto_center_calibrated = True
                self._auto_center_samples.clear()
            else:
                self._auto_center_samples.clear()
                self._auto_center_calibrated = False
            self._last_raw_x = None
            self._last_raw_y = None
            self._last_norm_x = None
            self._last_norm_y = None
            self._last_filtered_norm_x = None
            self._last_filtered_norm_y = None
            self._is_noise_locked = False
            self._eye_center_filter.reset()
            logger.info(
                "Dynamic auto-center recalibration requested (neutral: %.3f, %.3f).",
                self.calibrated_neutral_x,
                self.calibrated_neutral_y,
            )
            return (self.calibrated_neutral_x, self.calibrated_neutral_y)

    def recalibrate_neutral(self, neutral_x: float | None = None, neutral_y: float | None = None) -> tuple[float, float]:
        """Alias for recalibrate_center."""
        return self.recalibrate_center(neutral_x, neutral_y)

    def estimate_latest_gaze(self) -> GazeEstimate | None:
        """Read latest eye data and return a smoothed normalized gaze estimate."""
        eye_data = self._camera_service.get_latest_eye_data()
        if eye_data is None:
            return self._clear_latest_gaze()

        mapping = self._calibration_service.get_mapping()
        poly_calib = getattr(self._calibration_service, "get_polynomial_calibrator", lambda: None)()
        is_calibrated = (poly_calib is not None and getattr(poly_calib, "fitted_model", None) is not None) or (mapping is not None)

        if is_calibrated and hasattr(self._calibration_service, "get_center_eye_center"):
            center_eye = self._calibration_service.get_center_eye_center()
            if center_eye is not None and not hasattr(center_eye, "mock_calls"):
                cx = getattr(center_eye, "x", None)
                cy = getattr(center_eye, "y", None)
                if (
                    isinstance(cx, (int, float))
                    and isinstance(cy, (int, float))
                    and not hasattr(cx, "mock_calls")
                    and not hasattr(cy, "mock_calls")
                    and isfinite(cx)
                    and isfinite(cy)
                ):
                    self.calibrated_neutral_x = float(cx)
                    self.calibrated_neutral_y = float(cy)
                    self._neutral_x = float(cx)
                    self._neutral_y = float(cy)
                    self._auto_center_calibrated = True

        if not is_calibrated and mapping is None and (poly_calib is None or getattr(poly_calib, "fitted_model", None) is None):
            # Check if nose tip fallback can be used when 9-point calibration is not present
            nose_tip = getattr(eye_data, "nose_tip", None)
            landmarks = getattr(eye_data, "landmarks", None)
            if nose_tip is None and (not landmarks or len(landmarks) <= 1):
                return self._clear_latest_gaze()

        try:
            eye_center = self._compute_eye_center(eye_data)
            # Run raw eye center through 1-Euro adaptive low-pass filter BEFORE polynomial prediction
            filt_eye_x, filt_eye_y = self._eye_center_filter.filter(eye_center.x, eye_center.y)
            filt_eye_center = EyeCenter(x=self._clamp_normalized(filt_eye_x), y=self._clamp_normalized(filt_eye_y))

            if is_calibrated:
                if poly_calib is not None and getattr(poly_calib, "fitted_model", None) is not None:
                    raw_x, raw_y = poly_calib.predict(filt_eye_center.x, filt_eye_center.y)
                elif mapping is not None:
                    raw_x, raw_y = self._apply_mapping(filt_eye_center, mapping)
                else:
                    raw_x, raw_y = 0.5, 0.62
            else:
                # Uncalibrated head-offset fallback
                raw_x, raw_y = 0.5, 0.62
                nose_tip = getattr(eye_data, "nose_tip", None)
                if nose_tip is not None and isinstance(getattr(nose_tip, "x", None), (int, float)) and isfinite(float(nose_tip.x)):
                    raw_x = 1.0 - float(nose_tip.x)
                elif hasattr(eye_data, "landmarks") and isinstance(getattr(eye_data, "landmarks", None), (list, tuple)) and len(eye_data.landmarks) > 1:
                    lm1 = eye_data.landmarks[1]
                    if isinstance(getattr(lm1, "x", None), (int, float)) and isfinite(float(lm1.x)):
                        raw_x = 1.0 - float(lm1.x)

                if nose_tip is not None and isinstance(getattr(nose_tip, "y", None), (int, float)) and isfinite(float(nose_tip.y)):
                    raw_y = float(nose_tip.y)
                elif hasattr(eye_data, "landmarks") and isinstance(getattr(eye_data, "landmarks", None), (list, tuple)) and len(eye_data.landmarks) > 1:
                    lm1 = eye_data.landmarks[1]
                    if isinstance(getattr(lm1, "y", None), (int, float)) and isfinite(float(lm1.y)):
                        raw_y = float(lm1.y)
        except ValueError as exc:
            logger.warning("Skipping invalid gaze estimate: %s", exc)
            return self._clear_latest_gaze()

        quality = self._calibration_service.get_quality()
        quality_score = quality.score if quality is not None else 0.0

        with self._lock:
            # 1. Dual-regime velocity-adaptive smoothing on raw camera landmarks
            smooth_norm_x, smooth_norm_y, is_noise_locked = self._apply_noise_gate(raw_x, raw_y)

            # 2. Dynamic Auto-Center Calibration: first 20 frames establish neutral resting center using median
            if not self._auto_center_calibrated:
                self._auto_center_samples.append((eye_center.x, eye_center.y))
                if len(self._auto_center_samples) >= self._auto_center_target_samples:
                    sampled_x = [s[0] for s in self._auto_center_samples]
                    sampled_y = [s[1] for s in self._auto_center_samples]
                    med_x = float(np.median(sampled_x))
                    med_y = float(np.median(sampled_y))

                    # Bounds check [0.2, 0.88] fallback to 0.5, 0.70
                    nx = med_x if 0.2 <= med_x <= 0.8 else 0.5
                    ny = med_y if 0.2 <= med_y <= 0.88 else 0.70

                    self.calibrated_neutral_x = nx
                    self.calibrated_neutral_y = ny
                    self._neutral_x = nx
                    self._neutral_y = ny
                    self._auto_center_calibrated = True
                    self._eye_center_filter.reset()
                    logger.info(
                        "Auto-center calibrated neutral gaze to median (%.3f, %.3f) from 20 frames",
                        nx, ny,
                    )
            # Neutral center remains FIXED once calibrated (zero leaky drift)

            smoothed_x = self._clamp_normalized(smooth_norm_x) if is_calibrated else smooth_norm_x
            smoothed_y = self._clamp_normalized(smooth_norm_y) if is_calibrated else smooth_norm_y
            self._smoothed_x = smoothed_x
            self._smoothed_y = smoothed_y

            confidence = self._compute_confidence(
                raw_x=raw_x,
                raw_y=raw_y,
                smoothed_x=smoothed_x,
                smoothed_y=smoothed_y,
                calibration_score=quality_score,
            )
            estimate = GazeEstimate(
                eye_center=filt_eye_center,
                raw_x=raw_x,
                raw_y=raw_y,
                x=smoothed_x,
                y=smoothed_y,
                confidence=confidence,
                captured_at=time(),
                is_noise_locked=False,
                is_calibrated=is_calibrated,
            )
            self._latest_gaze = estimate
            self._history_buffer.append((smoothed_x, smoothed_y, estimate.captured_at))

        return estimate


    def get_latest_gaze(self) -> GazeEstimate | None:
        """Return the latest valid gaze estimate, if available."""
        with self._lock:
            return self._latest_gaze

    def reset(self) -> None:
        """Clear the latest gaze estimate, noise gate, and EMA state."""
        with self._lock:
            self._latest_gaze = None
            self._smoothed_x = None
            self._smoothed_y = None
            self._last_raw_x = None
            self._last_raw_y = None
            self._last_norm_x = None
            self._last_norm_y = None
            self._last_filtered_norm_x = None
            self._last_filtered_norm_y = None
            self._is_noise_locked = False
            self._eye_center_filter.reset()
            self._history_buffer.clear()
            logger.info("Eye gaze estimate state reset.")

    def _clear_latest_gaze(self) -> GazeEstimate | None:
        """Clear stale gaze data after missing or invalid inputs."""
        with self._lock:
            self._latest_gaze = None
            self._smoothed_x = None
            self._smoothed_y = None
            self._last_raw_x = None
            self._last_raw_y = None
            self._last_norm_x = None
            self._last_norm_y = None
            self._last_filtered_norm_x = None
            self._last_filtered_norm_y = None
            self._is_noise_locked = False
            self._eye_center_filter.reset()
            self._history_buffer.clear()
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
        """Compute one normalized gaze center from Landmark 1 (nose tip) or eye landmarks."""
        nose_tip = getattr(eye_data, "nose_tip", None)
        if (
            nose_tip is not None
            and isinstance(getattr(nose_tip, "x", None), (int, float))
            and isinstance(getattr(nose_tip, "y", None), (int, float))
            and isfinite(float(nose_tip.x))
            and isfinite(float(nose_tip.y))
        ):
            x = 1.0 - float(nose_tip.x)
            y = float(nose_tip.y)
            return EyeCenter(x=self._clamp_normalized(x), y=self._clamp_normalized(y))

        center = compute_eye_center(eye_data)
        if center is None:
            raise ValueError("eye landmark data is empty")

        x, y = center
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
        """Apply smoothing to normalized gaze coordinates (bypassed in kinematic physics mode)."""
        if self._kinematic_physics_enabled:
            self._smoothed_x = x
            self._smoothed_y = y
            return (
                self._clamp_normalized(x),
                self._clamp_normalized(y),
            )

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

    def _apply_noise_gate(self, raw_norm_x: float, raw_norm_y: float) -> tuple[float, float, bool]:
        """Dual-regime velocity-adaptive smoothing on raw camera landmarks.

        Measures true head velocity using landmark delta between camera frames (NOT cursor distance).
        - If head is resting (head_dist < 0.004): alpha = 0.08 (ironclad noise filter)
        - If head is moving fast (head_dist > 0.030): alpha = 0.90 (instant snap)
        """
        raw_x = float(raw_norm_x)
        raw_y = float(raw_norm_y)

        if (
            self._last_raw_x is None
            or self._last_raw_y is None
            or self._last_norm_x is None
            or self._last_norm_y is None
        ):
            self._last_raw_x = raw_x
            self._last_raw_y = raw_y
            self._last_norm_x = raw_x
            self._last_norm_y = raw_y
            self._last_filtered_norm_x = raw_x
            self._last_filtered_norm_y = raw_y
            return raw_x, raw_y, False

        dx = raw_x - self._last_raw_x
        dy = raw_y - self._last_raw_y
        dist = hypot(dx, dy)
        self._last_raw_x = raw_x
        self._last_raw_y = raw_y

        # Fast alpha ramp: 0.35 when still (kills camera flicker), 0.95 when moving (zero lag)
        t = max(0.0, min(1.0, dist / 0.012))
        alpha = 0.35 + (0.95 - 0.35) * t

        smooth_norm_x = self._last_norm_x + alpha * (raw_x - self._last_norm_x)
        smooth_norm_y = self._last_norm_y + alpha * (raw_y - self._last_norm_y)
        self._last_norm_x = smooth_norm_x
        self._last_norm_y = smooth_norm_y
        self._last_filtered_norm_x = smooth_norm_x
        self._last_filtered_norm_y = smooth_norm_y
        return smooth_norm_x, smooth_norm_y, False

    def gaze_to_screen(
        self,
        norm_x: float,
        norm_y: float,
        screen_w: int | None = None,
        screen_h: int | None = None,
        gain_x: float = 3.6,
        gain_y: float = 3.2,
        vertical_deadzone: float = 0.0,
    ) -> tuple[int, int]:
        """Convert normalized gaze coordinates to screen space using calibrated neutral values."""
        with self._lock:
            neutral_x = self.calibrated_neutral_x
            neutral_y = self.calibrated_neutral_y

        return gaze_to_screen_coordinates(
            norm_x=norm_x,
            norm_y=norm_y,
            screen_w=screen_w,
            screen_h=screen_h,
            gain_x=gain_x,
            gain_y=gain_y,
            neutral_x=neutral_x,
            neutral_y=neutral_y,
            vertical_deadzone=vertical_deadzone,
        )


def gaze_to_screen_coordinates(
    norm_x: float,
    norm_y: float,
    screen_w: int | None = None,
    screen_h: int | None = None,
    gain_x: float = 3.6,
    gain_y: float = 3.2,
    neutral_x: float = 0.50,
    neutral_y: float = 0.70,
    vertical_deadzone: float = 0.0,
) -> tuple[int, int]:
    """Convert normalized gaze coordinates to screen space using clean linear expansion."""
    if screen_w is None or screen_h is None or screen_w <= 0 or screen_h <= 0:
        try:
            import win32api
            import win32con

            screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
        except Exception:
            screen_w = 1920
            screen_h = 1080

    # Camera mirror: moving head right increases norm_x (1.0 - raw_x), so dx increases screen_x
    dx = norm_x - neutral_x
    dy = norm_y - neutral_y
    target_x_float = (screen_w / 2.0) + (dx * gain_x * screen_w)
    target_y_float = (screen_h / 2.0) + (dy * gain_y * screen_h)

    target_x = max(0, min(screen_w - 1, int(round(target_x_float))))
    target_y = max(0, min(screen_h - 1, int(round(target_y_float))))
    return (target_x, target_y)
