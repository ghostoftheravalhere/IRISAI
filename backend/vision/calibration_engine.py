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

# Standard 16-Point Screen Calibration Grid (4x4 Cartesian product, normalized screen coordinates)
SIXTEEN_POINT_GRID: tuple[tuple[float, float], ...] = (
    (0.1000, 0.1000),
    (0.3667, 0.1000),
    (0.6333, 0.1000),
    (0.9000, 0.1000),
    (0.1000, 0.3667),
    (0.3667, 0.3667),
    (0.6333, 0.3667),
    (0.9000, 0.3667),
    (0.1000, 0.6333),
    (0.3667, 0.6333),
    (0.6333, 0.6333),
    (0.9000, 0.6333),
    (0.1000, 0.9000),
    (0.3667, 0.9000),
    (0.6333, 0.9000),
    (0.9000, 0.9000),
)

# Independent 4-Point Validation Targets (held out from training design matrix)
FOUR_POINT_VALIDATION_GRID: tuple[tuple[float, float], ...] = (
    (0.2333, 0.7667),
    (0.7667, 0.7667),
    (0.5000, 0.5000),
    (0.2333, 0.2333),
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
    mean_u: float = 0.0
    mean_v: float = 0.0
    std_u: float = 1.0
    std_v: float = 1.0
    rank: int = 6
    condition_number: float = 1.0


from backend.vision.polynomial import PolynomialGazeModel, PolynomialGazeModelParams


class PolynomialCalibrator(PolynomialGazeModel):
    """2nd-degree 2D polynomial calibrator with input normalization and numerical safeguards."""

    def __init__(
        self,
        max_condition_number: float = 10000.0,
        head_comp_yaw: float = 0.003,
        head_comp_pitch: float = 0.003,
        head_comp_roll: float = 0.001,
    ) -> None:
        super().__init__(
            max_condition_number=max_condition_number,
            head_comp_yaw=head_comp_yaw,
            head_comp_pitch=head_comp_pitch,
            head_comp_roll=head_comp_roll,
        )
        self._fitted_model: PolynomialMappingResult | None = None

    @property
    def fitted_model(self) -> PolynomialMappingResult | None:
        """Return the currently fitted mapping result."""
        return self._fitted_model

    def reset(self) -> None:
        """Clear fitted parameters and normalization state."""
        super().reset()
        self._fitted_model = None

    def fit(self, samples: Sequence[CalibrationDataPoint]) -> PolynomialMappingResult:
        """Fit polynomial mapping with feature standardization and numerical safeguards."""
        self._fitted_model = None
        params = super().fit(samples)
        result = PolynomialMappingResult(
            x_weights=params.x_weights,
            y_weights=params.y_weights,
            anchor_pose=params.anchor_pose,
            rmse=params.rmse,
            r2_score=params.r2_score,
            sample_count=params.sample_count,
            degree=params.degree,
            head_comp_yaw=params.head_comp_yaw,
            head_comp_pitch=params.head_comp_pitch,
            head_comp_roll=params.head_comp_roll,
            mean_u=params.mean_u,
            mean_v=params.mean_v,
            std_u=params.std_u,
            std_v=params.std_v,
            rank=params.rank,
            condition_number=params.condition_number,
        )
        self._fitted_model = result
        return result

