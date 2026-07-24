"""
CameraService
Owner: Rehan (eye_tracking module)

Wraps OpenCV VideoCapture lifecycle.
Designed to be instantiated once and shared via FastAPI app state.
Eye tracking (MediaPipe) will consume this service in a later phase.
"""
import cv2
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class CameraService:
    def __init__(self, camera_index: int = 0) -> None:
        self._index = camera_index
        self._cap: cv2.VideoCapture | None = None

    # ── Public interface ───────────────────────────────────────────────────────

    def start(self) -> None:
        """Open the webcam. Raises RuntimeError if the device is unavailable."""
        if self.is_running:
            logger.debug("Camera already running on index %d", self._index)
            return

        cap = cv2.VideoCapture(self._index)
        if not cap.isOpened():
            cap.release()
            raise RuntimeError(f"Camera index {self._index} could not be opened.")

        self._cap = cap
        logger.info("Camera started on index %d", self._index)

    def stop(self) -> None:
        """Release the webcam. Safe to call even if already stopped."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Camera stopped.")

    @property
    def is_running(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def status(self) -> dict:
        return {
            "connected": self._probe_device(),
            "running": self.is_running,
            "camera_index": self._index,
        }

    # ── Internal ───────────────────────────────────────────────────────────────

    def _probe_device(self) -> bool:
        """
        Check whether the physical camera device exists without disturbing
        an already-running capture session.
        """
        if self.is_running:
            return True
        probe = cv2.VideoCapture(self._index)
        available = probe.isOpened()
        probe.release()
        return available
