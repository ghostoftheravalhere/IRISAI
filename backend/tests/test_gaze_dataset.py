"""Unit tests for Eye Gaze Dataset Collection & Validation Subsystem."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile

import numpy as np
import pytest

from backend.datasets.gaze.collector import GazeDatasetCollector
from backend.datasets.gaze.schema import GazeSampleMetadata, GazeTargetPoint
from backend.datasets.gaze.storage import GazeDatasetStorage
from backend.datasets.gaze.validator import GazeDatasetValidator
from backend.eye_tracking.face_mesh_service import EyeData, NormalizedLandmark


@pytest.fixture
def temp_dataset_dir():
    temp_dir = tempfile.mkdtemp(prefix="test_gaze_dataset_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_storage_and_metadata_serialization(temp_dataset_dir):
    storage = GazeDatasetStorage(base_dir=temp_dataset_dir)
    metadata = GazeSampleMetadata(
        sample_id="sample_001",
        user_id="user_test",
        session_id="session_test",
        target_index=0,
        target_x=0.1,
        target_y=0.1,
        screen_width=1920,
        screen_height=1080,
        left_image="",
        right_image="",
        eye_center_x=0.45,
        eye_center_y=0.55,
        confidence=1.0,
    )

    left_crop = np.zeros((64, 64, 3), dtype=np.uint8)
    right_crop = np.zeros((64, 64, 3), dtype=np.uint8)

    assert storage.save_sample(metadata, left_crop, right_crop) is True

    session_dir = temp_dataset_dir / "user_user_test" / "session_session_test"
    assert session_dir.exists()
    assert (session_dir / "images" / "sample_001_left.png").exists()
    assert (session_dir / "images" / "sample_001_right.png").exists()

    metadata_file = session_dir / "metadata.jsonl"
    assert metadata_file.exists()

    with open(metadata_file, "r", encoding="utf-8") as f:
        data = json.loads(f.readline())
        assert data["sample_id"] == "sample_001"
        assert data["user_id"] == "user_test"
        assert data["target_x"] == 0.1


def test_collector_sample_filtering_and_storage(temp_dataset_dir):
    storage = GazeDatasetStorage(base_dir=temp_dataset_dir)
    collector = GazeDatasetCollector(storage=storage, samples_per_target=5)
    collector.start_session(user_id="u1", session_id="s1")

    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # 1. Invalid EyeData (missing face) -> rejected
    success, msg = collector.process_frame(frame, None)
    assert success is False
    assert "Missing" in msg

    # 2. Valid EyeData -> accepted
    left_eye = tuple(NormalizedLandmark(index=i, x=0.4 + i * 0.01, y=0.5, z=0.0) for i in range(16))
    right_eye = tuple(NormalizedLandmark(index=i, x=0.6 + i * 0.01, y=0.5, z=0.0) for i in range(16))
    valid_eye_data = EyeData(left_eye=left_eye, right_eye=right_eye)

    success, msg = collector.process_frame(frame, valid_eye_data)
    assert success is True
    assert "accepted" in msg

    status = collector.get_status()
    assert status["total_accepted"] == 1
    assert status["total_rejected"] == 1

    collector.stop_session()


def test_dataset_validator(temp_dataset_dir):
    storage = GazeDatasetStorage(base_dir=temp_dataset_dir)
    metadata = GazeSampleMetadata(
        sample_id="sample_val_1",
        user_id="user_val",
        session_id="session_val",
        target_index=1,
        target_x=0.5,
        target_y=0.1,
        screen_width=1920,
        screen_height=1080,
        left_image="",
        right_image="",
        eye_center_x=0.5,
        eye_center_y=0.5,
        confidence=1.0,
    )
    left_crop = np.zeros((64, 64, 3), dtype=np.uint8)
    right_crop = np.zeros((64, 64, 3), dtype=np.uint8)
    storage.save_sample(metadata, left_crop, right_crop)

    validator = GazeDatasetValidator(base_dir=temp_dataset_dir)
    report = validator.validate_dataset()

    assert report.is_valid is True
    assert report.total_users == 1
    assert report.total_sessions == 1
    assert report.total_samples == 1
    assert report.missing_images == 0
