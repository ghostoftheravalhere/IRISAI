"""Eye calibration service for normalized eye landmark data."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from math import hypot, isfinite, sqrt
from statistics import median
from threading import RLock
from time import time

import numpy as np

from backend.core.config.eye_config import (
    LEFT_EAR_LANDMARK_INDICES as LEFT_EAR_INDICES,
    RIGHT_EAR_LANDMARK_INDICES as RIGHT_EAR_INDICES,
)
from backend.eye_tracking.eye_interaction_config import (
    EyeInteractionConfig,
    default_eye_interaction_config,
)
from backend.eye_tracking.face_mesh_service import (
    EyeData,
    LEFT_EYE_LANDMARK_INDICES,
    NormalizedLandmark,
    RIGHT_EYE_LANDMARK_INDICES,
)
from backend.utils.helpers import compute_eye_center
from backend.utils.logger import get_logger
from backend.vision.calibration_engine import (
    CalibrationDataPoint,
    FOUR_POINT_VALIDATION_GRID,
    NINE_POINT_GRID,
    PolynomialCalibrator,
    SIXTEEN_POINT_GRID,
)

logger = get_logger(__name__)

_EXPECTED_EYE_LANDMARKS = len(LEFT_EYE_LANDMARK_INDICES)
_MAD_TO_STD = 1.4826

@dataclass(frozen=True)
class CalibrationPoint:
    """Normalized screen-space calibration target."""

    index: int
    x: float
    y: float


# Standard 9-point screen calibration targets
NINE_CALIBRATION_POINTS: tuple[CalibrationPoint, ...] = tuple(
    CalibrationPoint(index=i, x=pt[0], y=pt[1])
    for i, pt in enumerate(NINE_POINT_GRID)
)

# Standard 16-point screen calibration training targets (4x4 grid: [0.1000, 0.3667, 0.6333, 0.9000])
SIXTEEN_CALIBRATION_POINTS: tuple[CalibrationPoint, ...] = tuple(
    CalibrationPoint(index=i, x=pt[0], y=pt[1])
    for i, pt in enumerate(SIXTEEN_POINT_GRID)
)

# Independent 4-point validation targets (held out from training dataset)
FOUR_VALIDATION_POINTS: tuple[CalibrationPoint, ...] = tuple(
    CalibrationPoint(index=16 + i, x=pt[0], y=pt[1])
    for i, pt in enumerate(FOUR_POINT_VALIDATION_GRID)
)


@dataclass(frozen=True)
class ValidationReport:
    """Independent post-fit validation evaluation on held-out targets."""

    mean_norm_error: float
    max_norm_error: float
    per_target_norm_errors: tuple[float, ...]
    mean_pixel_error: float | None = None
    max_pixel_error: float | None = None
    per_target_pixel_errors: tuple[float, ...] | None = None
    valid_sample_counts: tuple[int, ...] = field(default_factory=tuple)
    passed: bool = False
    description: str = "preliminary validation (4 held-out targets; not proof of full-screen accuracy)"


@dataclass(frozen=True)
class EyeCenter:
    """Normalized midpoint derived from left and right eye landmarks."""

    x: float
    y: float


@dataclass(frozen=True)
class CalibrationSample:
    """Eye landmark sample captured for one calibration target."""

    point: CalibrationPoint
    eye_data: EyeData
    eye_center: EyeCenter
    captured_at: float


@dataclass(frozen=True)
class CalibrationQuality:
    """Post-calibration fit quality and recalibration recommendation."""

    score: float
    rmse: float
    label: str
    recommend_recalibration: bool


@dataclass(frozen=True)
class CalibrationMapping:
    """Affine mapping from normalized eye center to normalized target point."""

    x_coefficients: tuple[float, float, float]
    y_coefficients: tuple[float, float, float]
    sample_count: int
    quality: CalibrationQuality | None = None


@dataclass(frozen=True)
class CalibrationProgress:
    """Current calibration progress."""

    current_point: CalibrationPoint | None
    completed_points: int
    total_points: int
    progress: float
    complete: bool
    quality: CalibrationQuality | None = None
    phase: str = "training"
    validation_report: ValidationReport | None = None
    is_calibrated: bool = False
    mode: str = "16-point"


@dataclass(frozen=True)
class CalibrationState:
    """Saved calibration state for future gaze/cursor tracking modules."""

    points: tuple[CalibrationPoint, ...]
    samples: tuple[CalibrationSample, ...]
    mapping: CalibrationMapping | None
    complete: bool
    updated_at: float
    quality: CalibrationQuality | None = None
    validation_report: ValidationReport | None = None
    is_calibrated: bool = False
    mode: str = "16-point"


class CalibrationCaptureError(ValueError):
    """Raised when a calibration point cannot be captured from stable samples."""


@dataclass
class EyeCalibrationService:
    """Guide and store an eye calibration flow with quadratic fitting and independent validation."""

    points: tuple[CalibrationPoint, ...] | None = None
    eye_config: EyeInteractionConfig | None = None
    mode: str | None = None

    def __post_init__(self) -> None:
        """Initialize mutable calibration state."""
        config = self.eye_config or default_eye_interaction_config()
        config.validate()
        object.__setattr__(self, "eye_config", config)

        # Resolve calibration mode
        active_mode = self.mode
        if active_mode is None:
            if self.points is not None:
                if len(self.points) == 9:
                    active_mode = "9-point"
                else:
                    active_mode = "16-point"
            elif config.calibration_mode:
                active_mode = config.calibration_mode
            else:
                active_mode = "16-point"

        if active_mode not in {"16-point", "9-point"}:
            active_mode = "16-point"

        object.__setattr__(self, "mode", active_mode)

        if active_mode == "9-point":
            train_pts = self.points if (self.points is not None and len(self.points) == 9) else NINE_CALIBRATION_POINTS
            val_pts: tuple[CalibrationPoint, ...] = ()
        else:
            train_pts = self.points if (self.points is not None and len(self.points) == 16) else SIXTEEN_CALIBRATION_POINTS
            val_pts = FOUR_VALIDATION_POINTS

        self.training_points: tuple[CalibrationPoint, ...] = train_pts
        self.validation_points: tuple[CalibrationPoint, ...] = val_pts
        self.points = train_pts + val_pts

        for point in self.points:
            if not 0.0 <= point.x <= 1.0 or not 0.0 <= point.y <= 1.0:
                raise ValueError("Calibration points must use normalized coordinates.")

        self._samples: list[CalibrationSample] = []
        self._validation_samples: list[CalibrationSample] = []
        self._validation_sample_counts: list[int] = []
        self._saved_state: CalibrationState | None = None
        self._mapping: CalibrationMapping | None = None
        self._polynomial_calibrator: PolynomialCalibrator | None = None
        self._quality: CalibrationQuality | None = None
        self._validation_report: ValidationReport | None = None
        self._is_calibrated: bool = False
        self._complete: bool = False
        self._phase: str = "training"
        self._lock = RLock()

    @property
    def is_calibrated(self) -> bool:
        """Return True if model fit and validation gates were successfully passed."""
        with self._lock:
            if (
                self._is_calibrated
                and self._polynomial_calibrator is not None
                and self._polynomial_calibrator.is_fitted
            ):
                return True
            total_samples = len(self._samples) + len(self._validation_samples)
            if (
                (self._complete or (total_samples == len(self.points) and len(self.points) > 0) or (len(self._samples) == len(self.points) and len(self.points) > 0))
                and (self._mapping is not None or self._polynomial_calibrator is not None)
                and (self._quality is not None and not self._quality.recommend_recalibration)
                and (self._validation_report is None or self._validation_report.passed)
            ):
                return True
            return False

    def restart(self, mode: str | None = None) -> CalibrationProgress:
        """Clear collected samples and restart calibration from the first point, optionally changing mode."""
        with self._lock:
            if mode is not None:
                if mode not in {"16-point", "9-point"}:
                    raise ValueError("calibration mode must be '16-point' or '9-point'.")
                object.__setattr__(self, "mode", mode)
                if mode == "9-point":
                    self.training_points = NINE_CALIBRATION_POINTS
                    self.validation_points = ()
                    self.points = NINE_CALIBRATION_POINTS
                else:
                    self.training_points = SIXTEEN_CALIBRATION_POINTS
                    self.validation_points = FOUR_VALIDATION_POINTS
                    self.points = SIXTEEN_CALIBRATION_POINTS + FOUR_VALIDATION_POINTS

            self._samples.clear()
            self._validation_samples.clear()
            self._validation_sample_counts.clear()
            self._saved_state = None
            self._mapping = None
            if self._polynomial_calibrator is not None:
                self._polynomial_calibrator.reset()
            self._polynomial_calibrator = None
            self._quality = None
            self._validation_report = None
            self._is_calibrated = False
            self._complete = False
            self._phase = "training"
            logger.info("Eye calibration restarted and state cleared (mode=%s).", self.mode)
            return self.get_progress()

    def reset(self, mode: str | None = None) -> CalibrationProgress:
        """Alias for restart."""
        return self.restart(mode=mode)

    def get_progress(self) -> CalibrationProgress:
        """Return the current calibration progress."""
        with self._lock:
            completed_train = len(self._samples)
            completed_val = len(self._validation_samples)
            total_train = len(self.training_points)
            total_val = len(self.validation_points)
            total = total_train + total_val
            completed = completed_train + completed_val

            complete_flag = self._complete or (
                len(self._samples) == len(self.points)
                and (self._mapping is not None or self._polynomial_calibrator is not None)
            )

            if completed_train < total_train:
                current_point = self.training_points[completed_train]
                phase = "training"
            elif total_val > 0 and completed_val < total_val:
                current_point = self.validation_points[completed_val]
                phase = "validation"
            else:
                current_point = None
                phase = "complete" if complete_flag else self._phase

            progress_val = completed / total if total > 0 else 0.0

            return CalibrationProgress(
                current_point=current_point,
                completed_points=completed,
                total_points=total,
                progress=progress_val,
                complete=complete_flag,
                quality=self._quality,
                phase=phase,
                validation_report=self._validation_report,
                is_calibrated=self.is_calibrated,
                mode=self.mode,
            )

    def get_quality(self) -> CalibrationQuality | None:
        """Return the latest calibration quality score, if available."""
        with self._lock:
            return self._quality

    def get_validation_report(self) -> ValidationReport | None:
        """Return the latest independent validation report, if available."""
        with self._lock:
            return self._validation_report

    def record_current_point(self, eye_data: EyeData) -> CalibrationProgress:
        """Store one eye frame for the current point (compat path)."""
        return self.record_current_point_from_samples((eye_data,))

    def record_current_point_from_samples(
        self,
        eye_samples: Sequence[EyeData],
    ) -> CalibrationProgress:
        """Average stable gaze samples and store one calibration point."""
        with self._lock:
            progress = self.get_progress()
            if progress.complete or progress.current_point is None:
                logger.info("Ignoring calibration sample; calibration is already complete.")
                return progress

            try:
                averaged_eye_data, eye_center, accepted = self._aggregate_stable_samples(
                    eye_samples
                )
            except CalibrationCaptureError as exc:
                logger.warning("Skipping unstable eye calibration capture: %s", exc)
                raise

            current_target = progress.current_point
            sample = CalibrationSample(
                point=current_target,
                eye_data=averaged_eye_data,
                eye_center=eye_center,
                captured_at=time(),
            )

            if len(self._samples) < len(self.training_points):
                # Recording training target sample
                self._samples.append(sample)
                logger.info(
                    "Captured eye calibration training sample %d/%d from %d averaged frames.",
                    len(self._samples),
                    len(self.training_points),
                    accepted,
                )

                if len(self._samples) == len(self.training_points):
                    # Fit quadratic polynomial model on all training points
                    try:
                        poly = PolynomialCalibrator(
                            max_condition_number=self.eye_config.calibration_max_condition_number
                        )
                        poly_pts = [
                            CalibrationDataPoint(
                                target_x=s.point.x,
                                target_y=s.point.y,
                                pupil_x=s.eye_center.x,
                                pupil_y=s.eye_center.y,
                            )
                            for s in self._samples
                        ]
                        poly.fit(poly_pts)
                        self._polynomial_calibrator = poly
                        self._quality = self._evaluate_quality(model=poly)
                        self._mapping = self._compute_mapping(self._samples)
                        logger.info(
                            "Fitted 2nd-degree PolynomialCalibrator on %d training points: rmse=%.4f, r2=%.4f, rank=%d, cond=%.2f",
                            len(poly_pts),
                            poly.fitted_model.rmse,
                            poly.fitted_model.r2_score,
                            poly.fitted_model.rank,
                            poly.fitted_model.condition_number,
                        )
                    except Exception as exc:
                        logger.warning("Polynomial calibration fitting failed: %s", exc)
                        self._polynomial_calibrator = None
                        self._mapping = None
                        self._quality = None
                        self._is_calibrated = False
                        self._complete = False
                        self._phase = "failed"
                        self.save_state()
                        return self.get_progress()

                    if len(self.validation_points) == 0:
                        # 9-point mode without validation points
                        if self._quality is not None and not self._quality.recommend_recalibration:
                            self._is_calibrated = True
                            self._complete = True
                            self._phase = "complete"
                        else:
                            self._is_calibrated = False
                            self._complete = False
                            self._phase = "failed"
                    else:
                        self._phase = "validation"
            else:
                # Recording validation target sample (kept strictly separate from training samples)
                self._validation_samples.append(sample)
                self._validation_sample_counts.append(accepted)
                logger.info(
                    "Captured eye calibration validation sample %d/%d from %d averaged frames.",
                    len(self._validation_samples),
                    len(self.validation_points),
                    accepted,
                )

                if len(self._validation_samples) == len(self.validation_points):
                    val_pts = [
                        CalibrationDataPoint(
                            target_x=s.point.x,
                            target_y=s.point.y,
                            pupil_x=s.eye_center.x,
                            pupil_y=s.eye_center.y,
                        )
                        for s in self._validation_samples
                    ]
                    sw, sh = None, None
                    try:
                        from backend.automation.controller import system_cursor
                        screen_w, screen_h = system_cursor.screen_size
                        if screen_w > 0 and screen_h > 0:
                            sw, sh = int(screen_w), int(screen_h)
                    except Exception:
                        pass

                    assert self._polynomial_calibrator is not None
                    metrics = self._polynomial_calibrator.evaluate_samples(
                        val_pts, screen_width=sw, screen_height=sh
                    )
                    mean_norm = float(metrics["mean_norm_error"])
                    max_norm = float(metrics["max_norm_error"])
                    passed = (
                        mean_norm <= self.eye_config.validation_mean_norm_threshold
                        and max_norm <= self.eye_config.validation_max_norm_threshold
                    )
                    self._validation_report = ValidationReport(
                        mean_norm_error=mean_norm,
                        max_norm_error=max_norm,
                        per_target_norm_errors=tuple(metrics["per_target_norm_errors"]),
                        mean_pixel_error=metrics.get("mean_pixel_error"),
                        max_pixel_error=metrics.get("max_pixel_error"),
                        per_target_pixel_errors=tuple(metrics["per_target_pixel_errors"]) if metrics.get("per_target_pixel_errors") else None,
                        valid_sample_counts=tuple(self._validation_sample_counts),
                        passed=passed,
                        description="preliminary validation (4 held-out targets; not proof of full-screen accuracy)",
                    )
                    if passed and self._quality is not None and not self._quality.recommend_recalibration:
                        self._is_calibrated = True
                        self._complete = True
                        self._phase = "complete"
                        logger.info(
                            "Calibration validation PASSED: mean_norm=%.4f (<=%.2f), max_norm=%.4f (<=%.2f)",
                            mean_norm,
                            self.eye_config.validation_mean_norm_threshold,
                            max_norm,
                            self.eye_config.validation_max_norm_threshold,
                        )
                    else:
                        self._is_calibrated = False
                        self._complete = False
                        self._phase = "failed"
                        logger.warning(
                            "Calibration validation FAILED: mean_norm=%.4f, max_norm=%.4f (gates: mean<=%.2f, max<=%.2f)",
                            mean_norm,
                            max_norm,
                            self.eye_config.validation_mean_norm_threshold,
                            self.eye_config.validation_max_norm_threshold,
                        )

            self.save_state()
            return self.get_progress()

    add_sample = record_current_point_from_samples

    def get_mapping(self) -> CalibrationMapping | None:
        """Return computed calibration mapping values, if calibration is complete."""
        with self._lock:
            return self._mapping

    def get_polynomial_calibrator(self) -> PolynomialCalibrator | None:
        """Return computed polynomial calibrator, if calibration is complete."""
        with self._lock:
            return self._polynomial_calibrator

    def get_center_eye_center(self) -> EyeCenter | None:
        """Return the calibrated eye center for Point 5 / center target (target (0.50, 0.50))."""
        with self._lock:
            for s in list(self._samples) + list(self._validation_samples):
                pt = getattr(s, "point", None)
                if pt is not None and abs(pt.x - 0.50) < 1e-2 and abs(pt.y - 0.50) < 1e-2:
                    return s.eye_center
            if self._saved_state and self._saved_state.samples:
                for s in self._saved_state.samples:
                    pt = getattr(s, "point", None)
                    if pt is not None and abs(pt.x - 0.50) < 1e-2 and abs(pt.y - 0.50) < 1e-2:
                        return s.eye_center
            return None

    def save_state(self) -> CalibrationState:
        """Save and return the current calibration state."""
        with self._lock:
            all_samples = tuple(self._samples) + tuple(self._validation_samples)
            self._saved_state = CalibrationState(
                points=self.points,
                samples=all_samples,
                mapping=self._mapping,
                complete=self._complete,
                updated_at=time(),
                quality=self._quality,
                validation_report=self._validation_report,
                is_calibrated=self.is_calibrated,
                mode=self.mode,
            )
            logger.info("Eye calibration state saved (mode=%s).", self.mode)
            return self._saved_state

    def get_state(self) -> CalibrationState:
        """Return the saved state, saving the current in-memory state if needed."""
        with self._lock:
            if self._saved_state is None:
                return self.save_state()
            return self._saved_state

    def _aggregate_stable_samples(
        self,
        eye_samples: Sequence[EyeData],
    ) -> tuple[EyeData, EyeCenter, int]:
        """Validate, reject outliers, and average consecutive gaze samples."""
        assert self.eye_config is not None
        progress = self.get_progress()
        current_pt = progress.current_point
        pt_idx = current_pt.index if current_pt else -1
        pt_x = current_pt.x if current_pt else 0.0
        pt_y = current_pt.y if current_pt else 0.0

        if not eye_samples:
            msg = "No eye landmark samples were collected from the camera stream."
            logger.warning(
                "[CALIBRATION DIAGNOSTIC] Point %d/9 Target: (%.2f, %.2f) FAILED: %s",
                pt_idx + 1, pt_x, pt_y, msg
            )
            raise CalibrationCaptureError(msg)

        valid_frames: list[EyeData] = []
        centers: list[EyeCenter] = []
        previous_center: EyeCenter | None = None
        invalid_landmark_or_blink_count = 0
        jump_rejected_count = 0

        for eye_data in eye_samples:
            if not self._is_valid_calibration_frame(eye_data):
                invalid_landmark_or_blink_count += 1
                continue

            try:
                center = self._compute_eye_center(eye_data)
            except ValueError:
                invalid_landmark_or_blink_count += 1
                continue

            if previous_center is not None:
                jump = hypot(center.x - previous_center.x, center.y - previous_center.y)
                if jump > self.eye_config.calibration_max_center_jump:
                    jump_rejected_count += 1
                    continue

            valid_frames.append(eye_data)
            centers.append(center)
            previous_center = center

        if len(valid_frames) < self.eye_config.calibration_min_valid_samples:
            if invalid_landmark_or_blink_count > len(valid_frames) and invalid_landmark_or_blink_count >= jump_rejected_count:
                reason = "Excessive blinking or lost eye tracking detected"
            elif jump_rejected_count > len(valid_frames):
                reason = "Unstable gaze or excessive eye movement detected"
            else:
                reason = "Insufficient valid gaze samples"

            exc_msg = (
                f"{reason}: only {len(valid_frames)} stable samples available "
                f"(processed {len(eye_samples)} frames, {invalid_landmark_or_blink_count} blinks/lost, {jump_rejected_count} jumps); "
                f"need at least {self.eye_config.calibration_min_valid_samples}."
            )
            logger.warning(
                "[CALIBRATION DIAGNOSTIC] Point %d Target: (%.2f, %.2f) FAILED: %s",
                pt_idx + 1, pt_x, pt_y, exc_msg
            )
            raise CalibrationCaptureError(exc_msg)

        kept_indices = self._select_inlier_indices(centers)
        outlier_rejected_count = len(valid_frames) - len(kept_indices)

        if len(kept_indices) < self.eye_config.calibration_min_valid_samples:
            exc_msg = (
                f"Unstable gaze dispersion: only {len(kept_indices)} inlier samples remained after outlier rejection "
                f"({outlier_rejected_count} outliers rejected from {len(valid_frames)} frames); "
                f"need at least {self.eye_config.calibration_min_valid_samples}."
            )
            logger.warning(
                "[CALIBRATION DIAGNOSTIC] Point %d Target: (%.2f, %.2f) FAILED: %s",
                pt_idx + 1, pt_x, pt_y, exc_msg
            )
            raise CalibrationCaptureError(exc_msg)

        kept_frames = [valid_frames[index] for index in kept_indices]
        kept_centers = [centers[index] for index in kept_indices]
        med_x = float(median(center.x for center in kept_centers))
        med_y = float(median(center.y for center in kept_centers))
        dispersion = sqrt(
            sum((center.x - med_x) ** 2 + (center.y - med_y) ** 2 for center in kept_centers)
            / len(kept_centers)
        )
        if dispersion > self.eye_config.calibration_max_sample_dispersion:
            exc_msg = (
                f"Gaze dispersion {dispersion:.4f} exceeds {self.eye_config.calibration_max_sample_dispersion:.4f}; "
                "hold still and look directly at the target."
            )
            logger.warning(
                "[CALIBRATION DIAGNOSTIC] Point %d Target: (%.2f, %.2f) FAILED: %s",
                pt_idx + 1, pt_x, pt_y, exc_msg
            )
            raise CalibrationCaptureError(exc_msg)

        averaged_eye_data = self._average_eye_data(kept_frames)
        eye_center = EyeCenter(x=med_x, y=med_y)
        logger.info(
            "[CALIBRATION DIAGNOSTIC] Point %d Target: (%.2f, %.2f) CAPTURED SUCCESSFULLY "
            "(frames=%d, valid=%d, inliers=%d, dispersion=%.4f, center=(%.4f, %.4f))",
            pt_idx + 1, pt_x, pt_y, len(eye_samples), len(valid_frames), len(kept_indices), dispersion, med_x, med_y
        )
        return averaged_eye_data, eye_center, len(kept_centers)

    def _is_valid_calibration_frame(self, eye_data: EyeData) -> bool:
        """Reject missing landmarks, blinks, and non-finite coordinates."""
        assert self.eye_config is not None
        if (
            len(eye_data.left_eye) != _EXPECTED_EYE_LANDMARKS
            or len(eye_data.right_eye) != _EXPECTED_EYE_LANDMARKS
        ):
            return False

        for landmark in eye_data.left_eye + eye_data.right_eye:
            if not (
                isfinite(landmark.x)
                and isfinite(landmark.y)
                and isfinite(landmark.z)
                and 0.0 <= landmark.x <= 1.0
                and 0.0 <= landmark.y <= 1.0
            ):
                return False

        try:
            left_ear = self._calculate_ear(eye_data.left_eye, LEFT_EAR_INDICES)
            right_ear = self._calculate_ear(eye_data.right_eye, RIGHT_EAR_INDICES)
        except ValueError:
            return False

        # Require both eyes open (not closed in a blink) so blink frames never enter the sample.
        min_ear = getattr(
            self.eye_config,
            "calibration_blink_ear_threshold",
            self.eye_config.ear_close_threshold,
        )
        return left_ear >= min_ear and right_ear >= min_ear

    def _select_inlier_indices(self, centers: Sequence[EyeCenter]) -> list[int]:
        """Keep samples within a robust MAD envelope around the median center."""
        assert self.eye_config is not None
        if len(centers) <= 2:
            return list(range(len(centers)))

        xs = [center.x for center in centers]
        ys = [center.y for center in centers]
        median_x = median(xs)
        median_y = median(ys)
        mad_x = median([abs(value - median_x) for value in xs])
        mad_y = median([abs(value - median_y) for value in ys])

        # Fall back to a small absolute floor when MAD collapses (very stable gaze).
        scale = self.eye_config.calibration_outlier_mad_scale * _MAD_TO_STD
        limit_x = max(mad_x * scale, 1e-4)
        limit_y = max(mad_y * scale, 1e-4)

        return [
            index
            for index, center in enumerate(centers)
            if abs(center.x - median_x) <= limit_x and abs(center.y - median_y) <= limit_y
        ]

    def _average_eye_data(self, eye_samples: Sequence[EyeData]) -> EyeData:
        """Average landmark coordinates across accepted frames."""
        return EyeData(
            left_eye=self._average_landmarks(
                [sample.left_eye for sample in eye_samples]
            ),
            right_eye=self._average_landmarks(
                [sample.right_eye for sample in eye_samples]
            ),
        )

    def _average_landmarks(
        self,
        landmark_groups: Sequence[tuple[NormalizedLandmark, ...]],
    ) -> tuple[NormalizedLandmark, ...]:
        """Aggregate corresponding landmarks across frames via component-wise median."""
        if not landmark_groups:
            raise CalibrationCaptureError("Cannot aggregate an empty landmark set.")

        landmark_count = len(landmark_groups[0])
        averaged: list[NormalizedLandmark] = []
        for landmark_index in range(landmark_count):
            points = [group[landmark_index] for group in landmark_groups]
            averaged.append(
                NormalizedLandmark(
                    index=points[0].index,
                    x=float(median(point.x for point in points)),
                    y=float(median(point.y for point in points)),
                    z=float(median(point.z for point in points)),
                )
            )
        return tuple(averaged)

    def _calculate_ear(
        self,
        landmarks: tuple[NormalizedLandmark, ...],
        indices: tuple[int, int, int, int, int, int],
    ) -> float:
        """Calculate Eye Aspect Ratio for blink rejection during capture."""
        points = {landmark.index: landmark for landmark in landmarks}
        try:
            p1, p2, p3, p4, p5, p6 = (points[index] for index in indices)
        except KeyError as exc:
            raise ValueError(f"missing EAR landmark index {exc.args[0]}") from exc

        vertical_1 = hypot(p2.x - p6.x, p2.y - p6.y)
        vertical_2 = hypot(p3.x - p5.x, p3.y - p5.y)
        horizontal = hypot(p1.x - p4.x, p1.y - p4.y)
        if horizontal <= 0.0:
            raise ValueError("horizontal eye distance is zero")

        ear = (vertical_1 + vertical_2) / (2.0 * horizontal)
        if not isfinite(ear):
            raise ValueError("EAR is not finite")
        return ear

    def _compute_eye_center(self, eye_data: EyeData) -> EyeCenter:
        """Compute one normalized eye-center point from both eyes."""
        # Sprint 1: shared helper removes duplicate eye-center averaging logic.
        center = compute_eye_center(eye_data)
        if center is None:
            raise ValueError("Cannot calibrate without eye landmarks.")

        x = center[0]
        nose = getattr(eye_data, "nose_tip", None)
        if nose is not None and isinstance(getattr(nose, "y", None), (int, float)) and isfinite(float(nose.y)):
            y = float(nose.y)
        else:
            y = center[1]

        if not isfinite(x) or not isfinite(y):
            raise ValueError("eye center contains non-finite coordinates")

        return EyeCenter(x=x, y=y)

    def _compute_mapping(self, samples: list[CalibrationSample]) -> CalibrationMapping | None:
        """Compute affine mapping values from eye centers to calibration points."""
        if len(samples) < 3:
            raise ValueError("At least 3 samples are required to compute calibration mapping.")

        inputs = np.array(
            [[sample.eye_center.x, sample.eye_center.y, 1.0] for sample in samples],
            dtype=float,
        )
        target_x = np.array([sample.point.x for sample in samples], dtype=float)
        target_y = np.array([sample.point.y for sample in samples], dtype=float)

        if np.linalg.matrix_rank(inputs) < 3:
            logger.warning("Eye calibration samples are degenerate; mapping was not computed.")
            return None

        try:
            x_coefficients = np.linalg.lstsq(inputs, target_x, rcond=None)[0]
            y_coefficients = np.linalg.lstsq(inputs, target_y, rcond=None)[0]
        except np.linalg.LinAlgError:
            logger.exception("Eye calibration mapping computation failed.")
            return None

        quality = self._evaluate_quality(
            samples=samples,
            x_coefficients=tuple(float(value) for value in x_coefficients),
            y_coefficients=tuple(float(value) for value in y_coefficients),
        )
        logger.info(
            "Computed eye calibration mapping from %d samples (quality=%s score=%.2f).",
            len(samples),
            quality.label,
            quality.score,
        )
        return CalibrationMapping(
            x_coefficients=tuple(float(value) for value in x_coefficients),
            y_coefficients=tuple(float(value) for value in y_coefficients),
            sample_count=len(samples),
            quality=quality,
        )

    def _evaluate_quality(
        self,
        samples: list[CalibrationSample] | None = None,
        x_coefficients: tuple[float, float, float] | None = None,
        y_coefficients: tuple[float, float, float] | None = None,
        model: PolynomialCalibrator | None = None,
    ) -> CalibrationQuality:
        """Score calibration fit using in-sample 2D RMSE against target points.

        RMSE = sqrt(mean(dx^2 + dy^2)) in normalized screen coordinates [0, 1].
        Score = 1 / (1 + rmse * calibration_rmse_scale), clamped to [0, 1].

        Labels (webcam usability interpretation; score formula unchanged):
        - good: score >= calibration_good_score_threshold
        - fair: score >= calibration_quality_threshold (cursor still usable)
        - poor: below threshold (recommend recalibration)
        """
        assert self.eye_config is not None
        if model is not None and model.fitted_model is not None:
            rmse = float(model.fitted_model.rmse)
        elif samples is not None and x_coefficients is not None and y_coefficients is not None:
            squared_error = 0.0
            for sample in samples:
                predicted_x = (
                    x_coefficients[0] * sample.eye_center.x
                    + x_coefficients[1] * sample.eye_center.y
                    + x_coefficients[2]
                )
                predicted_y = (
                    y_coefficients[0] * sample.eye_center.x
                    + y_coefficients[1] * sample.eye_center.y
                    + y_coefficients[2]
                )
                dx = predicted_x - sample.point.x
                dy = predicted_y - sample.point.y
                squared_error += dx * dx + dy * dy

            rmse = sqrt(squared_error / max(len(samples), 1))
        elif samples is not None and self._polynomial_calibrator is not None and self._polynomial_calibrator.fitted_model is not None:
            rmse = float(self._polynomial_calibrator.fitted_model.rmse)
        else:
            rmse = 1.0

        score = 1.0 / (1.0 + rmse * self.eye_config.calibration_rmse_scale)
        score = min(max(score, 0.0), 1.0)

        if score >= self.eye_config.calibration_good_score_threshold:
            label = "good"
        elif score >= self.eye_config.calibration_quality_threshold:
            label = "fair"
        else:
            label = "poor"

        return CalibrationQuality(
            score=score,
            rmse=rmse,
            label=label,
            recommend_recalibration=score < self.eye_config.calibration_quality_threshold,
        )
