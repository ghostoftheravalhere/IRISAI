"""Eye Gaze Dataset Collector Engine."""

from __future__ import annotations

from math import hypot, isfinite
from threading import RLock
import time
import uuid

import numpy as np

from backend.datasets.gaze.schema import GazeSampleMetadata, GazeTargetPoint
from backend.datasets.gaze.storage import GazeDatasetStorage
from backend.eye_tracking.face_mesh_service import EyeData, NormalizedLandmark
from backend.utils.helpers import compute_eye_center
from backend.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_TARGETS: tuple[GazeTargetPoint, ...] = (
    GazeTargetPoint(index=0, x=0.1, y=0.1, name="top-left"),
    GazeTargetPoint(index=1, x=0.5, y=0.1, name="top-center"),
    GazeTargetPoint(index=2, x=0.9, y=0.1, name="top-right"),
    GazeTargetPoint(index=3, x=0.1, y=0.5, name="middle-left"),
    GazeTargetPoint(index=4, x=0.5, y=0.5, name="center"),
    GazeTargetPoint(index=5, x=0.9, y=0.5, name="middle-right"),
    GazeTargetPoint(index=6, x=0.1, y=0.9, name="bottom-left"),
    GazeTargetPoint(index=7, x=0.5, y=0.9, name="bottom-center"),
    GazeTargetPoint(index=8, x=0.9, y=0.9, name="bottom-right"),
)


class GazeDatasetCollector:
    """Orchestrates sample collection across targets, filtering invalid frames and storing eye crops."""

    def __init__(
        self,
        storage: GazeDatasetStorage | None = None,
        samples_per_target: int = 30,
        ear_open_threshold: float = 0.18,
        max_jump_threshold: float = 0.15,
        targets: tuple[GazeTargetPoint, ...] = DEFAULT_TARGETS,
    ) -> None:
        self._storage = storage or GazeDatasetStorage()
        self._samples_per_target = samples_per_target
        self._ear_open_threshold = ear_open_threshold
        self._max_jump_threshold = max_jump_threshold
        self._targets = targets

        self._current_user_id = "user_01"
        self._current_session_id = "session_01"
        self._active = False
        self._current_target_index = 0
        self._accepted_count: dict[int, int] = {t.index: 0 for t in targets}
        self._rejected_count: dict[int, int] = {t.index: 0 for t in targets}
        self._last_eye_center: tuple[float, float] | None = None
        self._lock = RLock()

    def start_session(self, user_id: str = "user_01", session_id: str | None = None) -> dict:
        """Start a new collection session."""
        with self._lock:
            self._current_user_id = user_id
            self._current_session_id = session_id or f"sess_{int(time.time())}"
            self._active = True
            self._current_target_index = 0
            self._accepted_count = {t.index: 0 for t in self._targets}
            self._rejected_count = {t.index: 0 for t in self._targets}
            self._last_eye_center = None

            logger.info("Started gaze dataset session user=%s session=%s", user_id, self._current_session_id)
            return self.get_status()

    def process_frame(
        self,
        frame: np.ndarray,
        eye_data: EyeData | None,
        screen_size: tuple[int, int] = (1920, 1080),
        target_index: int | None = None,
    ) -> tuple[bool, str]:
        """Process one video frame for the current target and collect sample if valid."""
        with self._lock:
            if not self._active:
                return False, "Session not active"

            t_idx = target_index if target_index is not None else self._current_target_index
            if t_idx < 0 or t_idx >= len(self._targets):
                return False, "Invalid target index"

            target = self._targets[t_idx]
            if self._accepted_count[t_idx] >= self._samples_per_target:
                return False, "Target sample limit reached"

            # Rejection Checks
            if eye_data is None or not eye_data.left_eye or not eye_data.right_eye:
                self._rejected_count[t_idx] += 1
                return False, "Missing face/eye landmarks"

            center = compute_eye_center(eye_data)
            if center is None or not isfinite(center[0]) or not isfinite(center[1]):
                self._rejected_count[t_idx] += 1
                return False, "Invalid eye center coordinates"

            # Check blink / EAR
            left_ear = self._calculate_simple_ear(eye_data.left_eye)
            right_ear = self._calculate_simple_ear(eye_data.right_eye)
            if left_ear < self._ear_open_threshold or right_ear < self._ear_open_threshold:
                self._rejected_count[t_idx] += 1
                return False, "Blink detected"

            # Check head jump
            if self._last_eye_center is not None:
                jump = hypot(center[0] - self._last_eye_center[0], center[1] - self._last_eye_center[1])
                if jump > self._max_jump_threshold:
                    self._last_eye_center = center
                    self._rejected_count[t_idx] += 1
                    return False, "Excessive head movement / jump"

            self._last_eye_center = center

            # Crop eye bounding boxes from frame
            left_crop = self._crop_eye_region(frame, eye_data.left_eye)
            right_crop = self._crop_eye_region(frame, eye_data.right_eye)

            sample_id = f"sample_{uuid.uuid4().hex[:10]}"
            metadata = GazeSampleMetadata(
                sample_id=sample_id,
                user_id=self._current_user_id,
                session_id=self._current_session_id,
                target_index=target.index,
                target_x=target.x,
                target_y=target.y,
                screen_width=screen_size[0],
                screen_height=screen_size[1],
                left_image="",
                right_image="",
                eye_center_x=center[0],
                eye_center_y=center[1],
                confidence=1.0,
            )

            saved = self._storage.save_sample(metadata, left_crop, right_crop)
            if saved:
                self._accepted_count[t_idx] += 1
                return True, "Sample accepted"
            else:
                self._rejected_count[t_idx] += 1
                return False, "Storage save failed"

    def stop_session(self) -> dict:
        """Stop current collection session and return final status."""
        with self._lock:
            self._active = False
            logger.info("Stopped gaze dataset session user=%s session=%s", self._current_user_id, self._current_session_id)
            return self.get_status()

    def get_status(self) -> dict:
        """Return current collection session progress."""
        with self._lock:
            total_accepted = sum(self._accepted_count.values())
            total_rejected = sum(self._rejected_count.values())
            total_target = len(self._targets) * self._samples_per_target
            progress = (total_accepted / total_target) if total_target > 0 else 0.0

            return {
                "active": self._active,
                "user_id": self._current_user_id,
                "session_id": self._current_session_id,
                "current_target_index": self._current_target_index,
                "targets": [
                    {
                        "index": t.index,
                        "name": t.name,
                        "x": t.x,
                        "y": t.y,
                        "accepted": self._accepted_count[t.index],
                        "rejected": self._rejected_count[t.index],
                        "target_limit": self._samples_per_target,
                    }
                    for t in self._targets
                ],
                "total_accepted": total_accepted,
                "total_rejected": total_rejected,
                "progress_percent": round(progress * 100.0, 2),
            }

    @staticmethod
    def _calculate_simple_ear(landmarks: tuple[NormalizedLandmark, ...]) -> float:
        if len(landmarks) < 6:
            return 0.25
        p1, p2, p3, p4, p5, p6 = landmarks[:6]
        v1 = hypot(p2.x - p6.x, p2.y - p6.y)
        v2 = hypot(p3.x - p5.x, p3.y - p5.y)
        horiz = hypot(p1.x - p4.x, p1.y - p4.y)
        if horiz <= 0.0:
            return 0.0
        return (v1 + v2) / (2.0 * horiz)

    @staticmethod
    def _crop_eye_region(frame: np.ndarray, landmarks: tuple[NormalizedLandmark, ...], padding: int = 15) -> np.ndarray:
        if frame is None or frame.size == 0 or not landmarks:
            return np.zeros((64, 64, 3), dtype=np.uint8)

        h, w = frame.shape[:2]
        xs = [int(p.x * w) for p in landmarks]
        ys = [int(p.y * h) for p in landmarks]

        min_x = max(0, min(xs) - padding)
        max_x = min(w, max(xs) + padding)
        min_y = max(0, min(ys) - padding)
        max_y = min(h, max(ys) + padding)

        if max_x <= min_x or max_y <= min_y:
            return np.zeros((64, 64, 3), dtype=np.uint8)

        return frame[min_y:max_y, min_x:max_x].copy()
