"""MediaPipe Face Mesh processing for camera frames."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from threading import RLock
from typing import Any

import cv2
import mediapipe as mp
import numpy as np

from backend.utils.logger import get_logger

logger = get_logger(__name__)

LEFT_EYE_LANDMARK_INDICES = (
    362,
    382,
    381,
    380,
    374,
    373,
    390,
    249,
    263,
    466,
    388,
    387,
    386,
    385,
    384,
    398,
)
RIGHT_EYE_LANDMARK_INDICES = (
    33,
    7,
    163,
    144,
    145,
    153,
    154,
    155,
    133,
    173,
    157,
    158,
    159,
    160,
    161,
    246,
)


@dataclass(frozen=True)
class NormalizedLandmark:
    """Normalized Face Mesh landmark coordinate."""

    index: int
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class EyeData:
    """Reusable normalized eye landmark data for future cursor tracking."""

    left_eye: tuple[NormalizedLandmark, ...]
    right_eye: tuple[NormalizedLandmark, ...]


@dataclass(frozen=True)
class FaceMeshFrameResult:
    """Face Mesh processing output for a single camera frame."""

    frame: np.ndarray
    eye_data: EyeData | None


class FaceMeshService:
    """Detect a single face and draw all Face Mesh landmarks on frames."""

    def __init__(self) -> None:
        """Initialize the MediaPipe Face Mesh detector."""
        self._face_mesh: Any | None = None
        self._lock = RLock()

        try:
            self._face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=False,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        except Exception:
            logger.exception("Failed to initialize MediaPipe Face Mesh.")

    def process_frame(self, frame: np.ndarray) -> FaceMeshFrameResult:
        """Return a processed frame and normalized eye landmarks when available.

        MediaPipe expects RGB input while OpenCV captures BGR frames. Any
        processing failure is logged and the original frame is returned so the
        MJPEG stream can continue uninterrupted.
        """
        try:
            with self._lock:
                if self._face_mesh is None:
                    return FaceMeshFrameResult(frame=frame, eye_data=None)

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                rgb_frame.flags.writeable = False
                try:
                    results = self._face_mesh.process(rgb_frame)
                finally:
                    rgb_frame.flags.writeable = True
        except Exception:
            logger.exception("MediaPipe Face Mesh processing failed.")
            return FaceMeshFrameResult(frame=frame, eye_data=None)

        if not results.multi_face_landmarks:
            return FaceMeshFrameResult(frame=frame, eye_data=None)

        try:
            landmarks = results.multi_face_landmarks[0].landmark
            eye_data = self._extract_eye_data(landmarks)
            self._draw_landmarks(frame, landmarks)
        except ValueError as exc:
            logger.warning("Invalid Face Mesh landmark data: %s", exc)
            return FaceMeshFrameResult(frame=frame, eye_data=None)

        return FaceMeshFrameResult(frame=frame, eye_data=eye_data)

    def close(self) -> None:
        """Release MediaPipe resources."""
        with self._lock:
            if self._face_mesh is None:
                return

            try:
                self._face_mesh.close()
            except Exception:
                logger.exception("Failed to close MediaPipe Face Mesh resources.")
            finally:
                self._face_mesh = None

    def _draw_landmarks(self, frame: np.ndarray, landmarks: Sequence[Any]) -> None:
        """Draw every detected facial landmark as a point on the frame."""
        height, width = frame.shape[:2]

        for landmark in landmarks:
            if not isfinite(landmark.x) or not isfinite(landmark.y):
                continue

            x = min(max(int(landmark.x * width), 0), width - 1)
            y = min(max(int(landmark.y * height), 0), height - 1)
            cv2.circle(frame, (x, y), radius=1, color=(0, 255, 0), thickness=-1)

    def _extract_eye_data(self, landmarks: Sequence[Any]) -> EyeData:
        """Extract normalized left and right eye landmarks."""
        return EyeData(
            left_eye=self._extract_landmarks(landmarks, LEFT_EYE_LANDMARK_INDICES),
            right_eye=self._extract_landmarks(landmarks, RIGHT_EYE_LANDMARK_INDICES),
        )

    def _extract_landmarks(
        self,
        landmarks: Sequence[Any],
        indices: tuple[int, ...],
    ) -> tuple[NormalizedLandmark, ...]:
        """Extract normalized landmarks by Face Mesh index."""
        extracted: list[NormalizedLandmark] = []

        for index in indices:
            landmark = landmarks[index]
            extracted.append(
                NormalizedLandmark(
                    index=index,
                    x=self._clamp_normalized(landmark.x),
                    y=self._clamp_normalized(landmark.y),
                    z=self._validate_depth(landmark.z),
                )
            )

        return tuple(extracted)

    def _clamp_normalized(self, value: float) -> float:
        """Clamp MediaPipe's normalized x/y coordinate into the camera frame."""
        normalized = float(value)
        if not isfinite(normalized):
            raise ValueError("landmark coordinate is not finite")

        return min(max(normalized, 0.0), 1.0)

    def _validate_depth(self, value: float) -> float:
        """Return a finite landmark depth value."""
        depth = float(value)
        if not isfinite(depth):
            raise ValueError("landmark depth is not finite")

        return depth
