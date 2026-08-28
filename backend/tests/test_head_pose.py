"""Unit tests for Head-Pose Estimator (SolvePnP)."""

from __future__ import annotations

import math
import numpy as np
import pytest

from backend.vision.head_pose import FACE_MODEL_3D, KEYPOINT_INDICES, HeadPose, HeadPoseEstimator


def _project_3d_points(face_3d: np.ndarray, rvec: np.ndarray, tvec: np.ndarray, width: int = 640, height: int = 480) -> np.ndarray:
    """Helper to project 3D face points onto 2D image plane using camera matrix."""
    import cv2
    focal = float(width)
    cam_matrix = np.array(
        [[focal, 0.0, width / 2.0], [0.0, focal, height / 2.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    dist = np.zeros((4, 1), dtype=np.float64)
    proj, _ = cv2.projectPoints(face_3d, rvec, tvec, cam_matrix, dist)
    return proj.reshape(-1, 2)


def test_head_pose_neutral_face():
    """Verify neutral head pose estimation yields approximately zero pitch, yaw, roll."""
    estimator = HeadPoseEstimator(default_image_size=(640, 480))

    # Project standard face model at distance Z = 1000mm with zero rotation
    rvec_true = np.array([[0.0], [0.0], [0.0]], dtype=np.float64)
    tvec_true = np.array([[0.0], [0.0], [1000.0]], dtype=np.float64)
    pts_2d = _project_3d_points(FACE_MODEL_3D, rvec_true, tvec_true, 640, 480)

    # Convert to dictionary with landmark indices
    landmarks_dict = {idx: (pts_2d[i, 0], pts_2d[i, 1]) for i, idx in enumerate(KEYPOINT_INDICES)}

    pose = estimator.estimate_from_landmarks(landmarks_dict, image_size=(640, 480))
    assert pose is not None
    assert isinstance(pose, HeadPose)
    assert abs(pose.pitch) < 3.0
    assert abs(pose.yaw) < 3.0
    assert abs(pose.roll) < 3.0


def test_head_pose_yaw_rotation():
    """Verify yaw rotation estimation when head turns horizontally."""
    estimator = HeadPoseEstimator(default_image_size=(640, 480))

    # Apply 20 degree yaw rotation (around Y axis)
    import cv2
    yaw_deg = 20.0
    rot_mat, _ = cv2.Rodrigues(np.array([0.0, math.radians(yaw_deg), 0.0], dtype=np.float64))
    rvec_true, _ = cv2.Rodrigues(rot_mat)
    tvec_true = np.array([[0.0], [0.0], [1000.0]], dtype=np.float64)

    pts_2d = _project_3d_points(FACE_MODEL_3D, rvec_true, tvec_true, 640, 480)
    landmarks_dict = {idx: (pts_2d[i, 0], pts_2d[i, 1]) for i, idx in enumerate(KEYPOINT_INDICES)}

    pose = estimator.estimate_from_landmarks(landmarks_dict, image_size=(640, 480))
    assert pose is not None
    # Estimated yaw should match rotated angle within tolerance
    assert math.isclose(abs(pose.yaw), yaw_deg, abs_tol=4.0)


def test_head_pose_pitch_rotation():
    """Verify pitch rotation estimation when head tilts vertically."""
    estimator = HeadPoseEstimator(default_image_size=(640, 480))

    # Apply 15 degree pitch rotation (around X axis)
    import cv2
    pitch_deg = 15.0
    rot_mat, _ = cv2.Rodrigues(np.array([math.radians(pitch_deg), 0.0, 0.0], dtype=np.float64))
    rvec_true, _ = cv2.Rodrigues(rot_mat)
    tvec_true = np.array([[0.0], [0.0], [1000.0]], dtype=np.float64)

    pts_2d = _project_3d_points(FACE_MODEL_3D, rvec_true, tvec_true, 640, 480)
    landmarks_dict = {idx: (pts_2d[i, 0], pts_2d[i, 1]) for i, idx in enumerate(KEYPOINT_INDICES)}

    pose = estimator.estimate_from_landmarks(landmarks_dict, image_size=(640, 480))
    assert pose is not None
    assert math.isclose(abs(pose.pitch), pitch_deg, abs_tol=4.0)


def test_head_pose_roll_rotation():
    """Verify roll rotation estimation when head tilts sideways."""
    estimator = HeadPoseEstimator(default_image_size=(640, 480))

    # Apply 12 degree roll rotation (around Z axis)
    import cv2
    roll_deg = 12.0
    rot_mat, _ = cv2.Rodrigues(np.array([0.0, 0.0, math.radians(roll_deg)], dtype=np.float64))
    rvec_true, _ = cv2.Rodrigues(rot_mat)
    tvec_true = np.array([[0.0], [0.0], [1000.0]], dtype=np.float64)

    pts_2d = _project_3d_points(FACE_MODEL_3D, rvec_true, tvec_true, 640, 480)
    landmarks_dict = {idx: (pts_2d[i, 0], pts_2d[i, 1]) for i, idx in enumerate(KEYPOINT_INDICES)}

    pose = estimator.estimate_from_landmarks(landmarks_dict, image_size=(640, 480))
    assert pose is not None
    assert math.isclose(abs(pose.roll), roll_deg, abs_tol=4.0)


def test_head_pose_invalid_landmarks():
    """Verify invalid landmark formats return None gracefully."""
    estimator = HeadPoseEstimator()

    # Missing keypoints
    assert estimator.estimate_from_landmarks({1: (100, 100)}) is None

    # Empty array
    assert estimator.estimate_from_landmarks(np.array([])) is None

    # Non-finite values
    assert estimator.estimate_from_landmarks({idx: (float("nan"), 0.0) for idx in KEYPOINT_INDICES}) is None
