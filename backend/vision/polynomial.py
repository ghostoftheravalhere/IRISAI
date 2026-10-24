"""Unified 2nd-Degree Polynomial Gaze Model with Input Feature Normalization.

Fits a 6-parameter quadratic mapping from normalized eye pupil/center coordinates
to normalized screen coordinates using least squares, with active head-pose compensation,
matrix rank validation, and numerical condition-number safeguards.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Sequence

import numpy as np

from backend.utils.logger import get_logger
from backend.vision.head_pose import HeadPose

logger = get_logger(__name__)


@dataclass(frozen=True)
class HeadPoseAnchor:
    """Baseline reference head orientation captured during calibration."""

    pitch: float
    yaw: float
    roll: float


@dataclass(frozen=True)
class CalibrationDataPoint:
    """Individual gaze calibration sample pairing screen target with pupil/eye-center and head pose."""

    target_x: float
    target_y: float
    pupil_x: float
    pupil_y: float
    head_pose: HeadPose | tuple[float, float, float] | None = None
    weight: float = 1.0


@dataclass(frozen=True)
class PolynomialGazeModelParams:
    """Authoritative fitted polynomial model parameters, normalization statistics, and fit metrics."""

    x_weights: tuple[float, ...]  # (6,) quadratic polynomial weights for screen X
    y_weights: tuple[float, ...]  # (6,) quadratic polynomial weights for screen Y
    mean_u: float
    mean_v: float
    std_u: float
    std_v: float
    rank: int
    condition_number: float
    sample_count: int
    rmse: float
    r2_score: float
    degree: int = 2
    anchor_pose: HeadPoseAnchor | None = None
    head_comp_yaw: float = 0.003
    head_comp_pitch: float = 0.003
    head_comp_roll: float = 0.001


class PolynomialGazeModel:
    """Authoritative 2nd-degree 2D polynomial gaze model.

    Mathematical Formulation:
        1. Feature Standardization:
           Given input pupil/eye-center coordinates (u, v):
               u_norm = (u - mean_u) / std_u
               v_norm = (v - mean_v) / std_v
           Where near-zero standard deviations (< 1e-7) are clamped to 1.0.

        2. Quadratic Feature Basis:
           Phi(u_norm, v_norm) = [1, u_norm, v_norm, u_norm^2, v_norm^2, u_norm * v_norm]

        3. Normal Equations / Least Squares:
           Target screen coordinates T_x, T_y are fit via np.linalg.lstsq(Phi, T, rcond=None).
           Explicit matrix inversion is strictly avoided.

        4. Safeguards:
           - All inputs, targets, weights, and predictions are verified to be finite.
           - Matrix rank must equal the feature basis dimension (6 for quadratic, 3 for linear).
           - Condition number kappa(Phi) must not exceed max_condition_number (default 10,000).
    """

    def __init__(
        self,
        max_condition_number: float = 10000.0,
        head_comp_yaw: float = 0.003,
        head_comp_pitch: float = 0.003,
        head_comp_roll: float = 0.001,
    ) -> None:
        self.max_condition_number = float(max_condition_number)
        self.head_comp_yaw = float(head_comp_yaw)
        self.head_comp_pitch = float(head_comp_pitch)
        self.head_comp_roll = float(head_comp_roll)
        self._fitted_params: PolynomialGazeModelParams | None = None

    @property
    def fitted_model(self) -> PolynomialGazeModelParams | None:
        """Return the currently fitted model parameters, or None if uncalibrated."""
        return self._fitted_params

    @property
    def is_fitted(self) -> bool:
        """Return True if model is fitted and valid."""
        return self._fitted_params is not None

    def reset(self) -> None:
        """Clear fitted parameters and normalization state."""
        self._fitted_params = None

    @staticmethod
    def _build_features_2d(u_norm: np.ndarray, v_norm: np.ndarray) -> np.ndarray:
        """Construct 2nd-degree polynomial basis: [1, u, v, u^2, v^2, u*v]."""
        u_norm = np.asarray(u_norm, dtype=np.float64)
        v_norm = np.asarray(v_norm, dtype=np.float64)

        if u_norm.ndim == 0:
            return np.array(
                [1.0, float(u_norm), float(v_norm), float(u_norm**2), float(v_norm**2), float(u_norm * v_norm)],
                dtype=np.float64,
            )

        n = len(u_norm)
        ones = np.ones(n, dtype=np.float64)
        return np.column_stack([ones, u_norm, v_norm, u_norm**2, v_norm**2, u_norm * v_norm])

    @staticmethod
    def _build_features_linear(u_norm: np.ndarray, v_norm: np.ndarray) -> np.ndarray:
        """Construct 1st-degree affine linear basis: [1, u, v]."""
        u_norm = np.asarray(u_norm, dtype=np.float64)
        v_norm = np.asarray(v_norm, dtype=np.float64)

        if u_norm.ndim == 0:
            return np.array([1.0, float(u_norm), float(v_norm)], dtype=np.float64)

        n = len(u_norm)
        ones = np.ones(n, dtype=np.float64)
        return np.column_stack([ones, u_norm, v_norm])

    def compute_anchor_pose(self, samples: Sequence[CalibrationDataPoint]) -> HeadPoseAnchor | None:
        """Establish the baseline reference head orientation from calibration samples."""
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
        """Compensate pupil coordinates for head orientation delta relative to anchor pose."""
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

        comp_x = pupil_x - (self.head_comp_yaw * delta_yaw) - (self.head_comp_roll * delta_roll)
        comp_y = pupil_y - (self.head_comp_pitch * delta_pitch)

        return (float(comp_x), float(comp_y))

    def fit(self, samples: Sequence[CalibrationDataPoint]) -> PolynomialGazeModelParams:
        """Fit polynomial mapping with feature standardization and numerical safeguards.

        Args:
            samples: Sequence of CalibrationDataPoint observations.

        Returns:
            PolynomialGazeModelParams containing fitted coefficients and quality metrics.

        Raises:
            ValueError: If samples are non-finite, insufficient, rank-deficient, or ill-conditioned.
        """
        # Invalidate any previously fitted model immediately so a failed fit cannot leave a stale model active
        self._fitted_params = None

        min_samples = 6
        if len(samples) < min_samples:
            raise ValueError(f"At least 6 calibration samples required for quadratic polynomial fitting, got {len(samples)}")

        # 1. Establish Head-Pose Anchor
        anchor = self.compute_anchor_pose(samples)

        # 2. Extract and compensate pupil inputs, validate finiteness
        raw_u = []
        raw_v = []
        target_x = []
        target_y = []

        for idx, s in enumerate(samples):
            if not (math.isfinite(s.pupil_x) and math.isfinite(s.pupil_y)):
                raise ValueError(f"Sample index {idx} contains non-finite pupil coordinates: ({s.pupil_x}, {s.pupil_y})")
            if not (math.isfinite(s.target_x) and math.isfinite(s.target_y)):
                raise ValueError(f"Sample index {idx} contains non-finite target coordinates: ({s.target_x}, {s.target_y})")

            cu, cv = self.compensate_pupil(s.pupil_x, s.pupil_y, s.head_pose, anchor)
            if not (math.isfinite(cu) and math.isfinite(cv)):
                raise ValueError(f"Sample index {idx} produced non-finite compensated pupil coordinates: ({cu}, {cv})")

            raw_u.append(cu)
            raw_v.append(cv)
            target_x.append(s.target_x)
            target_y.append(s.target_y)

        u_arr = np.array(raw_u, dtype=np.float64)
        v_arr = np.array(raw_v, dtype=np.float64)
        tx_arr = np.array(target_x, dtype=np.float64)
        ty_arr = np.array(target_y, dtype=np.float64)

        # 3. Calculate Input Normalization Statistics (mean, std)
        mean_u = float(np.mean(u_arr))
        mean_v = float(np.mean(v_arr))
        std_u = float(np.std(u_arr))
        std_v = float(np.std(v_arr))

        # Safe guard for zero or near-zero variance
        if std_u < 1e-7:
            std_u = 1.0
        if std_v < 1e-7:
            std_v = 1.0

        u_norm = (u_arr - mean_u) / std_u
        v_norm = (v_arr - mean_v) / std_v

        # 4. Construct Feature Basis: Quadratic [1, u, v, u^2, v^2, uv]
        degree = 2
        phi = self._build_features_2d(u_norm, v_norm)
        num_features = 6

        # 5. Matrix Rank Check
        matrix_rank = int(np.linalg.matrix_rank(phi))
        if matrix_rank < num_features:
            raise ValueError(
                f"Design matrix is rank-deficient (rank={matrix_rank} < {num_features}). "
                "Calibration samples may be collinear or contain insufficient spatial spread."
            )

        # 6. Condition Number Check
        cond = float(np.linalg.cond(phi))
        if not math.isfinite(cond) or cond > self.max_condition_number:
            raise ValueError(
                f"Design matrix is ill-conditioned (condition number={cond:.2f} > {self.max_condition_number:.2f}). "
                "Feature matrix cannot be inverted stably."
            )

        # 7. Numerically Stable Least Squares Fitting (np.linalg.lstsq)
        wx, _, _, _ = np.linalg.lstsq(phi, tx_arr, rcond=None)
        wy, _, _, _ = np.linalg.lstsq(phi, ty_arr, rcond=None)

        if not (np.all(np.isfinite(wx)) and np.all(np.isfinite(wy))):
            raise ValueError("Least-squares solution produced non-finite polynomial coefficients.")

        # 8. Compute Fit Quality Metrics (RMSE and R^2)
        pred_x = phi @ wx
        pred_y = phi @ wy

        sq_err = (tx_arr - pred_x) ** 2 + (ty_arr - pred_y) ** 2
        rmse = float(np.sqrt(np.mean(sq_err)))

        total_var = float(np.var(tx_arr) + np.var(ty_arr))
        res_var = float(np.mean(sq_err))
        r2 = max(0.0, 1.0 - (res_var / (total_var + 1e-9)))

        params = PolynomialGazeModelParams(
            x_weights=tuple(float(w) for w in wx),
            y_weights=tuple(float(w) for w in wy),
            mean_u=mean_u,
            mean_v=mean_v,
            std_u=std_u,
            std_v=std_v,
            rank=matrix_rank,
            condition_number=cond,
            sample_count=len(samples),
            rmse=rmse,
            r2_score=float(r2),
            degree=degree,
            anchor_pose=anchor,
            head_comp_yaw=self.head_comp_yaw,
            head_comp_pitch=self.head_comp_pitch,
            head_comp_roll=self.head_comp_roll,
        )

        self._fitted_params = params
        logger.info(
            "PolynomialGazeModel fit successful: degree=%d, samples=%d, rank=%d, cond=%.2f, rmse=%.4f, r2=%.4f",
            degree,
            len(samples),
            matrix_rank,
            cond,
            rmse,
            r2,
        )
        return params

    def predict(
        self,
        pupil_x: float,
        pupil_y: float,
        current_head_pose: HeadPose | tuple[float, float, float] | None = None,
        clamp_to_bounds: bool = True,
    ) -> tuple[float, float]:
        """Predict screen coordinates using authoritative stored normalization and weights.

        Args:
            pupil_x: Eye pupil or eye-center normalized horizontal position.
            pupil_y: Eye pupil or eye-center normalized vertical position.
            current_head_pose: Optional active head pose for rotation drift compensation.
            clamp_to_bounds: If True, clamp output to normalized screen bounds [0.0, 1.0].

        Returns:
            (screen_x, screen_y) normalized coordinates.

        Raises:
            ValueError: If model is not fitted or input coordinates are non-finite.
        """
        if self._fitted_params is None:
            raise ValueError("Calibrator has not been fitted. Call fit() first.")

        if not (math.isfinite(pupil_x) and math.isfinite(pupil_y)):
            raise ValueError(f"Non-finite input coordinates received for prediction: ({pupil_x}, {pupil_y})")

        m = self._fitted_params

        # 1. Compensate for head pose rotation delta
        comp_x, comp_y = self.compensate_pupil(pupil_x, pupil_y, current_head_pose, m.anchor_pose)

        # 2. Standardize using EXACT stored statistics
        u_norm = (comp_x - m.mean_u) / m.std_u
        v_norm = (comp_y - m.mean_v) / m.std_v

        # 3. Construct Feature Vector
        if m.degree == 2:
            feat = self._build_features_2d(np.array(u_norm), np.array(v_norm))
        else:
            feat = self._build_features_linear(np.array(u_norm), np.array(v_norm))

        # 4. Predict
        wx = np.array(m.x_weights, dtype=np.float64)
        wy = np.array(m.y_weights, dtype=np.float64)

        pred_x = float(np.dot(feat, wx))
        pred_y = float(np.dot(feat, wy))

        if not (math.isfinite(pred_x) and math.isfinite(pred_y)):
            raise ValueError(f"Prediction produced non-finite output: ({pred_x}, {pred_y})")

        if clamp_to_bounds:
            pred_x = min(max(pred_x, 0.0), 1.0)
            pred_y = min(max(pred_y, 0.0), 1.0)

        return (pred_x, pred_y)

    def evaluate_samples(
        self,
        samples: Sequence[CalibrationDataPoint],
        screen_width: int | None = None,
        screen_height: int | None = None,
    ) -> dict[str, Any]:
        """Evaluate fitted model on test/validation samples without updating model parameters.

        Returns:
            Dictionary containing:
                - mean_norm_error: float
                - max_norm_error: float
                - per_target_norm_errors: list[float]
                - mean_pixel_error: float | None
                - max_pixel_error: float | None
                - per_target_pixel_errors: list[float] | None
        """
        if self._fitted_params is None:
            raise ValueError("Model must be fitted before evaluating validation samples.")

        norm_errors: list[float] = []
        pixel_errors: list[float] = []
        has_screen_dims = (
            screen_width is not None
            and screen_height is not None
            and screen_width > 0
            and screen_height > 0
        )

        for s in samples:
            pred_x, pred_y = self.predict(s.pupil_x, s.pupil_y, s.head_pose, clamp_to_bounds=False)
            dx = s.target_x - pred_x
            dy = s.target_y - pred_y
            e_norm = math.hypot(dx, dy)
            norm_errors.append(e_norm)

            if has_screen_dims:
                px_err = math.hypot(dx * screen_width, dy * screen_height)
                pixel_errors.append(px_err)

        mean_norm = float(np.mean(norm_errors)) if norm_errors else 0.0
        max_norm = float(np.max(norm_errors)) if norm_errors else 0.0
        mean_px = float(np.mean(pixel_errors)) if pixel_errors else None
        max_px = float(np.max(pixel_errors)) if pixel_errors else None

        return {
            "mean_norm_error": mean_norm,
            "max_norm_error": max_norm,
            "per_target_norm_errors": norm_errors,
            "mean_pixel_error": mean_px,
            "max_pixel_error": max_px,
            "per_target_pixel_errors": pixel_errors if has_screen_dims else None,
        }
