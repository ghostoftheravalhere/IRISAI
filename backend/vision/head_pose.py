"""Head-Pose Estimator using SolvePnP on MediaPipe Face Mesh landmarks."""

from __future__ import annotations

from dataclasses import dataclass
from math import degrees, isfinite
from typing import Any, Sequence

import cv2
import numpy as np

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Standard 3D Generic Anthropometric Face Model Keypoints (in mm relative to nose tip)
# 1: Nose Tip, 152: Chin, 263: Left Eye Outer, 33: Right Eye Outer, 291: Left Mouth, 61: Right Mouth
FACE_MODEL_3D = np.array(
    [
        [0.0, 0.0, 0.0],          # Nose tip (landmark 1)
        [0.0, -330.0, -65.0],     # Chin (landmark 152)
        [225.0, 170.0, -135.0],   # Left eye outer corner (landmark 263)
        [-225.0, 170.0, -135.0],  # Right eye outer corner (landmark 33)
        [150.0, -150.0, -125.0],  # Left mouth corner (landmark 291)
        [-150.0, -150.0, -125.0], # Right mouth corner (landmark 61)
    ],
    dtype=np.float64,
)

KEYPOINT_INDICES = (1, 152, 263, 33, 291, 61)


@dataclass(frozen=True)
class HeadPose:
    """Estimated head orientation and translation vectors."""

    pitch: float  # Rotation around X-axis (looking up/down) in degrees
    yaw: float    # Rotation around Y-axis (looking left/right) in degrees
    roll: float   # Rotation around Z-axis (tilting head side-to-side) in degrees
    rvec: np.ndarray  # (3, 1) Rodrigues rotation vector
    tvec: np.ndarray  # (3, 1) Translation vector
    rotation_matrix: np.ndarray  # (3, 3) Rotation matrix

    def as_dict(self) -> dict[str, Any]:
        """Convert head pose to dictionary format."""
        return {
            "pitch": round(self.pitch, 3),
            "yaw": round(self.yaw, 3),
            "roll": round(self.roll, 3),
            "tx": round(float(self.tvec[0, 0]), 3),
            "ty": round(float(self.tvec[1, 0]), 3),
            "tz": round(float(self.tvec[2, 0]), 3),
        }


class HeadPoseEstimator:
    """Estimates real-time 3D head pose using cv2.solvePnP on 2D facial landmarks."""

    def __init__(self, default_image_size: tuple[int, int] = (640, 480)) -> None:
        """Initialize head pose estimator with reference 3D face model."""
        self._image_width = default_image_size[0]
        self._image_height = default_image_size[1]
        self._face_3d = np.copy(FACE_MODEL_3D)

    def _build_camera_matrix(self, width: int, height: int) -> tuple[np.ndarray, np.ndarray]:
        """Construct intrinsic camera calibration matrix and zero distortion coefficients."""
        focal_length = float(width)
        center_x = width / 2.0
        center_y = height / 2.0

        camera_matrix = np.array(
            [
                [focal_length, 0.0, center_x],
                [0.0, focal_length, center_y],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        dist_coeffs = np.zeros((4, 1), dtype=np.float64)
        return camera_matrix, dist_coeffs

    def estimate_from_landmarks(
        self,
        landmarks: dict[int, tuple[float, float]] | Sequence[Any] | np.ndarray,
        image_size: tuple[int, int] | None = None,
    ) -> HeadPose | None:
        """Estimate head pose from full or indexed facial landmarks.

        Args:
            landmarks: Either a dict mapping landmark index -> (x, y),
                       a sequence of landmark objects with .x, .y attributes,
                       or an (N, 2) numpy array.
            image_size: (width, height) in pixels. Defaults to initialized size.

        Returns:
            HeadPose instance with pitch, yaw, roll, or None if estimation fails.
        """
        img_w, img_h = image_size if image_size is not None else (self._image_width, self._image_height)
        if img_w <= 0 or img_h <= 0:
            return None

        # Extract the 6 canonical keypoint coordinates in pixel space
        points_2d = []

        if isinstance(landmarks, dict):
            for idx in KEYPOINT_INDICES:
                if idx not in landmarks:
                    return None
                lx, ly = landmarks[idx]
                px = lx * img_w if 0.0 <= lx <= 1.0 else lx
                py = ly * img_h if 0.0 <= ly <= 1.0 else ly
                points_2d.append([px, py])

        elif isinstance(landmarks, (list, tuple)):
            # Check if landmark objects or indexed items
            try:
                for idx in KEYPOINT_INDICES:
                    lm = landmarks[idx]
                    lx = getattr(lm, "x", None)
                    ly = getattr(lm, "y", None)
                    if lx is None or ly is None:
                        if isinstance(lm, (list, tuple, np.ndarray)) and len(lm) >= 2:
                            lx, ly = float(lm[0]), float(lm[1])
                        else:
                            return None
                    px = lx * img_w if 0.0 <= lx <= 1.0 else lx
                    py = ly * img_h if 0.0 <= ly <= 1.0 else ly
                    points_2d.append([px, py])
            except (IndexError, TypeError):
                return None

        elif isinstance(landmarks, np.ndarray):
            if landmarks.shape[0] < max(KEYPOINT_INDICES) + 1:
                if landmarks.shape[0] == len(KEYPOINT_INDICES):
                    # Already subset of 6 keypoints
                    for row in landmarks:
                        lx, ly = float(row[0]), float(row[1])
                        px = lx * img_w if 0.0 <= lx <= 1.0 else lx
                        py = ly * img_h if 0.0 <= ly <= 1.0 else ly
                        points_2d.append([px, py])
                else:
                    return None
            else:
                for idx in KEYPOINT_INDICES:
                    lx, ly = float(landmarks[idx, 0]), float(landmarks[idx, 1])
                    px = lx * img_w if 0.0 <= lx <= 1.0 else lx
                    py = ly * img_h if 0.0 <= ly <= 1.0 else ly
                    points_2d.append([px, py])
        else:
            return None

        face_2d = np.array(points_2d, dtype=np.float64)

        if not np.all(np.isfinite(face_2d)):
            return None

        camera_matrix, dist_coeffs = self._build_camera_matrix(img_w, img_h)

        try:
            success, rvec, tvec = cv2.solvePnP(
                self._face_3d,
                face_2d,
                camera_matrix,
                dist_coeffs,
                flags=cv2.SOLVEPNP_ITERATIVE,
            )
            if not success:
                return None

            rot_mat, _ = cv2.Rodrigues(rvec)

            # Decompose rotation matrix into Euler angles (Pitch, Yaw, Roll)
            angles, _, _, _, _, _ = cv2.RQDecomp3x3(rot_mat)
            pitch = float(angles[0] * 360.0) if abs(angles[0]) < 1.0 else float(angles[0])
            yaw = float(angles[1] * 360.0) if abs(angles[1]) < 1.0 else float(angles[1])
            roll = float(angles[2] * 360.0) if abs(angles[2]) < 1.0 else float(angles[2])

            return HeadPose(
                pitch=pitch,
                yaw=yaw,
                roll=roll,
                rvec=rvec,
                tvec=tvec,
                rotation_matrix=rot_mat,
            )
        except Exception as exc:
            logger.debug("SolvePnP estimation failed: %s", exc)
            return None
