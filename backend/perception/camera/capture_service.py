"""OpenCV camera capture lifecycle wrapper."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


class CaptureService:
    """Single owner of the managed OpenCV ``VideoCapture`` instance."""

    def __init__(self, camera_index: int) -> None:
        self._camera_index = camera_index
        self._capture: cv2.VideoCapture | None = None

    @property
    def camera_index(self) -> int:
        """Return the configured camera index."""
        return self._camera_index

    @property
    def is_open(self) -> bool:
        """Return whether the managed capture is currently open."""
        return self._capture is not None and self._capture.isOpened()

    def open(self) -> bool:
        """Create one OpenCV capture for the configured camera index."""
        if self.is_open:
            return True

        self._capture = cv2.VideoCapture(self._camera_index)
        return self.is_open

    def read(self) -> tuple[bool, np.ndarray | None]:
        """Read one frame from the managed capture."""
        if self._capture is None or not self._capture.isOpened():
            return False, None
        return self._capture.read()

    def release(self) -> None:
        """Release the managed capture if it exists."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def get_property(self, prop_id: int) -> float:
        """Return an OpenCV capture property value."""
        if self._capture is None:
            return 0.0
        return float(self._capture.get(prop_id))

    def set_property(self, prop_id: int, value: Any) -> bool:
        """Set an OpenCV capture property value."""
        if self._capture is None:
            return False
        return bool(self._capture.set(prop_id, value))
