"""Eye Gaze Dataset Storage Manager."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from backend.datasets.gaze.schema import GazeSampleMetadata
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GazeDatasetStorage:
    """Manages directory hierarchy, eye image crop saves, and JSONL metadata records."""

    def __init__(self, base_dir: Path | str = "dataset/gaze") -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def get_session_dir(self, user_id: str, session_id: str) -> Path:
        """Return path to session directory: base_dir/user_<id>/session_<id>/."""
        clean_user = "".join(c for c in user_id if c.isalnum() or c in ("_", "-")) or "default"
        clean_session = "".join(c for c in session_id if c.isalnum() or c in ("_", "-")) or "default"
        session_dir = self._base_dir / f"user_{clean_user}" / f"session_{clean_session}"
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "images").mkdir(parents=True, exist_ok=True)
        return session_dir

    def save_sample(
        self,
        metadata: GazeSampleMetadata,
        left_eye_crop: np.ndarray,
        right_eye_crop: np.ndarray,
        crop_size: tuple[int, int] = (64, 64),
    ) -> bool:
        """Save left and right eye crop images as PNG and append metadata to JSONL."""
        try:
            session_dir = self.get_session_dir(metadata.user_id, metadata.session_id)
            images_dir = session_dir / "images"

            # Resize crops to fixed size if valid
            if left_eye_crop is not None and left_eye_crop.size > 0:
                resized_left = cv2.resize(left_eye_crop, crop_size)
            else:
                resized_left = np.zeros((*crop_size, 3), dtype=np.uint8)

            if right_eye_crop is not None and right_eye_crop.size > 0:
                resized_right = cv2.resize(right_eye_crop, crop_size)
            else:
                resized_right = np.zeros((*crop_size, 3), dtype=np.uint8)

            left_rel_path = f"images/{metadata.sample_id}_left.png"
            right_rel_path = f"images/{metadata.sample_id}_right.png"

            cv2.imwrite(str(images_dir / f"{metadata.sample_id}_left.png"), resized_left)
            cv2.imwrite(str(images_dir / f"{metadata.sample_id}_right.png"), resized_right)

            metadata.left_image = left_rel_path
            metadata.right_image = right_rel_path

            # Append to metadata.jsonl
            metadata_file = session_dir / "metadata.jsonl"
            with open(metadata_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(metadata.to_dict()) + "\n")

            return True
        except Exception:
            logger.exception("Failed to save gaze sample %s", metadata.sample_id)
            return False
