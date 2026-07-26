"""Unit tests for eye calibration sampling and quality scoring."""

from __future__ import annotations

import sys
from types import ModuleType

# Keep these tests runnable without OpenCV/MediaPipe installed in the env.
if "cv2" not in sys.modules:
    sys.modules["cv2"] = ModuleType("cv2")
if "mediapipe" not in sys.modules:
    mediapipe = ModuleType("mediapipe")
    mediapipe.solutions = ModuleType("mediapipe.solutions")
    sys.modules["mediapipe"] = mediapipe
    sys.modules["mediapipe.solutions"] = mediapipe.solutions

import pytest

from backend.eye_tracking.calibration import (
    CalibrationCaptureError,
    CalibrationPoint,
    CalibrationSample,
    EyeCalibrationService,
    EyeCenter,
)
from backend.eye_tracking.eye_interaction_config import EyeInteractionConfig
from backend.eye_tracking.face_mesh_service import (
    LEFT_EYE_LANDMARK_INDICES,
    RIGHT_EYE_LANDMARK_INDICES,
    EyeData,
    NormalizedLandmark,
)

# MediaPipe EAR landmark order used by EyeCalibrationService.
_RIGHT_EAR = (33, 160, 158, 133, 153, 144)
_LEFT_EAR = (362, 385, 387, 263, 373, 380)


def _landmarks_for_eye(
    indices: tuple[int, ...],
    ear_indices: tuple[int, int, int, int, int, int],
    *,
    cx: float,
    cy: float,
    open_eye: bool = True,
) -> tuple[NormalizedLandmark, ...]:
    """Build eye landmarks with valid EAR geometry around ``(cx, cy)``."""
    half_width = 0.020
    half_height = 0.012 if open_eye else 0.002
    p1, p2, p3, p4, p5, p6 = ear_indices
    positioned = {
        p1: (cx - half_width, cy),
        p4: (cx + half_width, cy),
        p2: (cx - half_width * 0.35, cy - half_height),
        p3: (cx + half_width * 0.35, cy - half_height),
        p6: (cx - half_width * 0.35, cy + half_height),
        p5: (cx + half_width * 0.35, cy + half_height),
    }

    points: list[NormalizedLandmark] = []
    for index in indices:
        x, y = positioned.get(index, (cx, cy))
        points.append(NormalizedLandmark(index=index, x=x, y=y, z=0.0))
    return tuple(points)


def _eye_data(*, cx: float, cy: float, open_eye: bool = True) -> EyeData:
    """Create synthetic binocular eye data centered near ``(cx, cy)``."""
    return EyeData(
        left_eye=_landmarks_for_eye(
            LEFT_EYE_LANDMARK_INDICES,
            _LEFT_EAR,
            cx=cx + 0.02,
            cy=cy,
            open_eye=open_eye,
        ),
        right_eye=_landmarks_for_eye(
            RIGHT_EYE_LANDMARK_INDICES,
            _RIGHT_EAR,
            cx=cx - 0.02,
            cy=cy,
            open_eye=open_eye,
        ),
    )


def test_aggregate_stable_samples_averages_and_rejects_outliers() -> None:
    """Multi-sample capture should average inliers and drop jump/outlier frames."""
    config = EyeInteractionConfig(
        calibration_min_valid_samples=8,
        calibration_outlier_mad_scale=2.5,
        calibration_max_center_jump=0.035,
        calibration_max_sample_dispersion=0.02,
    )
    service = EyeCalibrationService(eye_config=config)

    samples = [_eye_data(cx=0.50, cy=0.45) for _ in range(20)]
    samples[5] = _eye_data(cx=0.62, cy=0.45)  # sudden jump
    samples[8] = _eye_data(cx=0.50, cy=0.45, open_eye=False)  # blink

    averaged, center, accepted = service._aggregate_stable_samples(samples)

    assert accepted >= config.calibration_min_valid_samples
    assert abs(center.x - 0.50) < 0.01
    assert abs(center.y - 0.45) < 0.01
    assert len(averaged.left_eye) == len(LEFT_EYE_LANDMARK_INDICES)


def test_aggregate_rejects_unstable_dispersion() -> None:
    """Wandering gaze should fail capture instead of writing a noisy point."""
    config = EyeInteractionConfig(
        calibration_min_valid_samples=8,
        calibration_max_sample_dispersion=0.005,
        calibration_max_center_jump=0.05,
    )
    service = EyeCalibrationService(eye_config=config)
    samples = [
        _eye_data(cx=0.50 + ((index % 5) - 2) * 0.008, cy=0.45)
        for index in range(20)
    ]

    with pytest.raises(CalibrationCaptureError, match="dispersion"):
        service._aggregate_stable_samples(samples)


def test_quality_score_formula_and_thresholds() -> None:
    """Score math is unchanged; labels reflect webcam cursor usability bands."""
    config = EyeInteractionConfig(
        calibration_rmse_scale=5.0,
        calibration_quality_threshold=0.45,
        calibration_good_score_threshold=0.58,
    )
    service = EyeCalibrationService(eye_config=config)

    perfect_samples = [
        CalibrationSample(
            point=CalibrationPoint(index=index, x=x, y=y),
            eye_data=_eye_data(cx=x, cy=y),
            eye_center=EyeCenter(x=x, y=y),
            captured_at=0.0,
        )
        for index, (x, y) in enumerate(
            [
                (0.1, 0.1),
                (0.5, 0.1),
                (0.9, 0.1),
                (0.1, 0.5),
                (0.5, 0.5),
                (0.9, 0.5),
                (0.1, 0.9),
                (0.5, 0.9),
                (0.9, 0.9),
            ]
        )
    ]
    quality = service._evaluate_quality(
        samples=perfect_samples,
        x_coefficients=(1.0, 0.0, 0.0),
        y_coefficients=(0.0, 1.0, 0.0),
    )
    assert quality.rmse == pytest.approx(0.0)
    assert quality.score == pytest.approx(1.0)
    assert quality.label == "good"
    assert quality.recommend_recalibration is False

    # Constant residual length ≈ 0.10 → score = 1/(1+0.5) ≈ 0.667 (good for webcam).
    offset_x = 0.07
    offset_y = 0.071418485
    noisy = [
        CalibrationSample(
            point=sample.point,
            eye_data=sample.eye_data,
            eye_center=EyeCenter(
                x=sample.eye_center.x + offset_x,
                y=sample.eye_center.y + offset_y,
            ),
            captured_at=0.0,
        )
        for sample in perfect_samples
    ]
    quality = service._evaluate_quality(
        samples=noisy,
        x_coefficients=(1.0, 0.0, 0.0),
        y_coefficients=(0.0, 1.0, 0.0),
    )
    assert quality.rmse == pytest.approx(0.10, abs=0.001)
    assert quality.score == pytest.approx(1.0 / (1.0 + 0.10 * 5.0), abs=0.005)
    assert quality.label == "good"
    assert quality.recommend_recalibration is False

    # Typical reported webcam residual ≈ score 0.48 → fair / usable, not poor.
    fair = service._evaluate_quality(
        samples=[
            CalibrationSample(
                point=sample.point,
                eye_data=sample.eye_data,
                eye_center=EyeCenter(
                    x=sample.eye_center.x + 0.153,
                    y=sample.eye_center.y + 0.153,
                ),
                captured_at=0.0,
            )
            for sample in perfect_samples
        ],
        x_coefficients=(1.0, 0.0, 0.0),
        y_coefficients=(0.0, 1.0, 0.0),
    )
    assert fair.score == pytest.approx(0.48, abs=0.02)
    assert fair.label == "fair"
    assert fair.recommend_recalibration is False


def test_gaze_confidence_does_not_collapse_from_clamped_jitter() -> None:
    """Out-of-range raw mapping should soften confidence, not invent huge jitter."""
    from backend.eye_tracking.gaze_service import EyeGazeService

    confidence = EyeGazeService._compute_confidence(  # type: ignore[arg-type]
        object.__new__(EyeGazeService),
        raw_x=1.4,
        raw_y=0.5,
        smoothed_x=1.0,
        smoothed_y=0.5,
        calibration_score=0.7,
    )
    # Previous formula used raw vs clamped EMA → stability 0 and confidence ~0.31.
    assert confidence >= 0.40
