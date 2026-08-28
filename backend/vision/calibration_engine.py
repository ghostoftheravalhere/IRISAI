"""9-Point Polynomial Calibration & Head-Pose Compensation Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Sequence

import numpy as np

from backend.utils.logger import get_logger
from backend.vision.head_pose import HeadPose

logger = get_logger(__name__)

# Standard 9-Point Screen Calibration Grid (normalized screen coordinates)
NINE_POINT_GRID: tuple[tuple[float, float], ...] = (
    (0.1, 0.1),  # Top-Left
    (0.5, 0.1),  # Top-Center
    (0.9, 0.1),  # Top-Right
    (0.1, 0.5),  # Middle-Left
    (0.5, 0.5),  # Center
    (0.9, 0.5),  # Middle-Right
    (0.1, 0.9),  # Bottom-Left
    (0.5, 0.9),  # Bottom-Center
    (0.9, 0.9),  # Bottom-Right
)


@dataclass(frozen=True)
class CalibrationDataPoint:
    """Individual gaze calibration sample pairing screen target with pupil and head pose."""

    target_x: float
    target_y: float
    pupil_x: float
    pupil_y: float
    head_pose: HeadPose | tuple[float, float, float] | None = None
    weight: float = 1.0


@dataclass(frozen=True)
class HeadPoseAnchor:
    """Baseline reference head orientation captured during calibration."""

    pitch: float
    yaw: float
    roll: float


@dataclass(frozen=True)
class PolynomialMappingResult:
    """Fitted polynomial mapping model parameters and calibration quality."""

    x_weights: tuple[float, ...]  # (6,) polynomial coefficients
    y_weights: tuple[float, ...]  # (6,) polynomial coefficients
    anchor_pose: HeadPoseAnchor | None
    rmse: float
    r2_score: float
    sample_count: int
    degree: int = 2
    head_comp_yaw: float = 0.003
    head_comp_pitch: float = 0.003
    head_comp_roll: float = 0.001


class PolynomialCalibrator:
    """2nd-degree 2D polynomial calibrator with active 3D head-pose compensation."""

    def __init__(
        self,
        head_comp_yaw: float = 0.003,
        head_comp_pitch: float = 0.003,
        head_comp_roll: float = 0.001,
    ) -> None:
        """Initialize polynomial calibrator.

        Args:
            head_comp_yaw: Pupil correction factor per degree of yaw rotation.
            head_comp_pitch: Pupil correction factor per degree of pitch rotation.
            head_comp_roll: Pupil correction factor per degree of roll rotation.
        """
        self._head_comp_yaw = float(head_comp_yaw)
        self._head_comp_pitch = float(head_comp_pitch)
        self._head_comp_roll = float(head_comp_roll)
        self._fitted_model: PolynomialMappingResult | None = None

    @property
    def fitted_model(self) -> PolynomialMappingResult | None:
        """Return the currently fitted mapping result."""
        return self._fitted_model

    @staticmethod
    def _build_features_2d(px: float | np.ndarray, py: float | np.ndarray) -> np.ndarray:
        """Construct 2nd-degree polynomial basis: [1, x, y, x^2, y^2, x*y]."""
        px = np.asarray(px, dtype=np.float64)
        py = np.asarray(py, dtype=np.float64)

        if px.ndim == 0:
            return np.array([1.0, float(px), float(py), float(px ** 2), float(py ** 2), float(px * py)], dtype=np.float64)

        n = len(px)
        ones = np.ones(n, dtype=np.float64)
        return np.column_stack([ones, px, py, px ** 2, py ** 2, px * py])

    @staticmethod
    def _build_features_linear(px: float | np.ndarray, py: float | np.ndarray) -> np.ndarray:
        """Construct 1st-degree affine linear basis: [1, x, y]."""
        px = np.asarray(px, dtype=np.float64)
        py = np.asarray(py, dtype=np.float64)

        if px.ndim == 0:
            return np.array([1.0, float(px), float(py)], dtype=np.float64)

        n = len(px)
        ones = np.ones(n, dtype=np.float64)
        return np.column_stack([ones, px, py])

    def compute_anchor_pose(self, samples: Sequence[CalibrationDataPoint]) -> HeadPoseAnchor | None:
        """Establish the baseline reference head pose (anchor) from calibration samples."""
        pitches, yaws, rolls = [], [], []
        for s in samples:
            if s.head_pose is not None:
                if isinstance(s.head_pose, HeadPose):
                    pitches.append(s.head_pose.pitch)
                    yaws.append(s.head_pose.yaw)
                    rolls.append(s.head_pose.roll)
                elif isinstance(s.head_pose, (list, tuple)) and len(s.head_pose) >= 3:
                    pitches.append(float(s.head_pose[0]))
                    yaws.append(float(s.head_pose[1]))
                    rolls.append(float(s.head_pose[2]))

        if not pitches:
            return None

        return HeadPoseAnchor(
            pitch=float(np.median(pitches)),
            yaw=float(np.median(yaws)),
            roll=float(np.median(rolls)),
        )

    def compensate_pupil(
        self,
        pupil_x: float,
        pupil_y: float,
        current_pose: HeadPose | tuple[float, float, float] | None,
        anchor_pose: HeadPoseAnchor | None,
    ) -> tuple[float, float]:
        """Subtract real-time head-pose delta from pupil coordinates before polynomial evaluation."""
        if current_pose is None or anchor_pose is None:
            return (pupil_x, pupil_y)

        if isinstance(current_pose, HeadPose):
            cur_p, cur_y, cur_r = current_pose.pitch, current_pose.yaw, current_pose.roll
        elif isinstance(current_pose, (list, tuple)) and len(current_pose) >= 3:
            cur_p, cur_y, cur_r = float(current_pose[0]), float(current_pose[1]), float(current_pose[2])
        else:
            return (pupil_x, pupil_y)

        delta_pitch = cur_p - anchor_pose.pitch
        delta_yaw = cur_y - anchor_pose.yaw
        delta_roll = cur_r - anchor_pose.roll

        # Compensate for head rotation drift
        comp_x = pupil_x - (self._head_comp_yaw * delta_yaw) - (self._head_comp_roll * delta_roll)
        comp_y = pupil_y - (self._head_comp_pitch * delta_pitch)

        return (float(comp_x), float(comp_y))

    def fit(self, samples: Sequence[CalibrationDataPoint]) -> PolynomialMappingResult:
        """Fit polynomial mapping with head-pose compensation using least squares.

        Args:
            samples: List of CalibrationDataPoint instances.

        Returns:
            PolynomialMappingResult with fitted weights and fit diagnostics.
        """
        if len(samples) < 3:
            raise ValueError(f"At least 3 calibration samples required for fitting, got {len(samples)}")

        # 1. Establish Head-Pose Anchor
        anchor = self.compute_anchor_pose(samples)

        # 2. Extract and compensate pupil inputs
        pupil_xs = []
        pupil_ys = []
        target_xs = []
        target_ys = []

        for s in samples:
            cx, cy = self.compensate_pupil(s.pupil_x, s.pupil_y, s.head_pose, anchor)
            pupil_xs.append(cx)
            pupil_ys.append(cy)
            target_xs.append(s.target_x)
            target_ys.append(s.target_y)

        px = np.array(pupil_xs, dtype=np.float64)
        py = np.array(pupil_ys, dtype=np.float64)
        tx = np.array(target_xs, dtype=np.float64)
        ty = np.array(target_ys, dtype=np.float64)

        # 3. Choose polynomial degree based on sample count
        degree = 2 if len(samples) >= 6 else 1

        if degree == 2:
            a_mat = self._build_features_2d(px, py)
        else:
            a_mat = self._build_features_linear(px, py)

        # 4. Least-squares fitting: A * w = t
        wx, residuals_x, _, _ = np.linalg.lstsq(a_mat, tx, rcond=None)
        wy, residuals_y, _, _ = np.linalg.lstsq(a_mat, ty, rcond=None)

        # 5. Evaluate quality metrics (RMSE and R^2)
        pred_x = a_mat @ wx
        pred_y = a_mat @ wy

        err_x = tx - pred_x
        err_y = ty - pred_y
        sq_errors = err_x ** 2 + err_y ** 2
        rmse = float(np.sqrt(np.mean(sq_errors)))

        # R^2 calculation
        total_var = np.var(tx) + np.var(ty)
        res_var = np.mean(sq_errors)
        r2 = max(0.0, 1.0 - (res_var / (total_var + 1e-9)))

        result = PolynomialMappingResult(
            x_weights=tuple(float(w) for w in wx),
            y_weights=tuple(float(w) for w in wy),
            anchor_pose=anchor,
            rmse=rmse,
            r2_score=float(r2),
            sample_count=len(samples),
            degree=degree,
            head_comp_yaw=self._head_comp_yaw,
            head_comp_pitch=self._head_comp_pitch,
            head_comp_roll=self._head_comp_roll,
        )

        self._fitted_model = result
        logger.info(
            "Polynomial calibration fit complete: degree=%d, samples=%d, rmse=%.4f, r2=%.4f",
            degree,
            len(samples),
            rmse,
            r2,
        )
        return result

    def predict(
        self,
        pupil_x: float,
        pupil_y: float,
        current_head_pose: HeadPose | tuple[float, float, float] | None = None,
    ) -> tuple[float, float]:
        """Predict screen coordinates from pupil position with head-pose compensation."""
        if self._fitted_model is None:
            raise ValueError("Calibrator has not been fitted. Call fit() first.")

        model = self._fitted_model

        # 1. Compensate for head pose delta
        comp_x, comp_y = self.compensate_pupil(
            pupil_x,
            pupil_y,
            current_head_pose,
            model.anchor_pose,
        )

        # 2. Build polynomial feature vector
        if model.degree == 2:
            feat = self._build_features_2d(comp_x, comp_y)
        else:
            feat = self._build_features_linear(comp_x, comp_y)

        # 3. Evaluate polynomial
        wx = np.array(model.x_weights, dtype=np.float64)
        wy = np.array(model.y_weights, dtype=np.float64)

        screen_x = float(np.dot(feat, wx))
        screen_y = float(np.dot(feat, wy))

        # Clamp to valid normalized screen range [0, 1]
        clamped_x = min(max(screen_x, 0.0), 1.0)
        clamped_y = min(max(screen_y, 0.0), 1.0)

        return (clamped_x, clamped_y)
