"""Camera service for managing the OpenCV webcam capture lifecycle."""

import cv2

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class CameraServiceError(RuntimeError):
    """Raised when a camera lifecycle operation cannot be completed."""

    def __init__(self, message: str, status_code: int) -> None:
        """Create a service error with its matching HTTP status code."""
        super().__init__(message)
        self.status_code = status_code


class CameraService:
    """Single owner of the OpenCV ``VideoCapture`` instance.

    The service is instantiated once by the FastAPI application and shared via
    ``app.state``. It never creates a secondary probe capture; status is
    derived from the managed capture and the last known start result.
    """

    def __init__(self, camera_index: int = 0) -> None:
        """Create a camera service for the configured OpenCV camera index."""
        self._index = camera_index
        self._capture: cv2.VideoCapture | None = None
        self._last_known_connected = False

    def start(self) -> dict[str, bool | int]:
        """Start the webcam capture and return the latest camera status.

        Raises:
            CameraServiceError: If the camera is already running or cannot be
                opened by OpenCV.
        """
        if self.is_running:
            message = f"Camera index {self._index} is already running."
            logger.warning(message)
            raise CameraServiceError(message, status_code=409)

        self._capture = cv2.VideoCapture(self._index)
        if not self._capture.isOpened():
            self._release_capture()
            self._last_known_connected = False
            message = f"Camera index {self._index} could not be opened."
            logger.error(message)
            raise CameraServiceError(message, status_code=503)

        self._last_known_connected = True
        logger.info("Camera started on index %d", self._index)
        return self.status()

    def stop(self) -> dict[str, bool | int]:
        """Stop the webcam capture and return the latest camera status.

        Raises:
            CameraServiceError: If no capture session is currently running.
        """
        if not self.is_running:
            message = f"Camera index {self._index} is not running."
            logger.warning(message)
            raise CameraServiceError(message, status_code=409)

        self._release_capture()
        logger.info("Camera stopped on index %d", self._index)
        return self.status()

    def cleanup(self) -> None:
        """Release camera resources during application shutdown."""
        if self._capture is not None:
            self._release_capture()
            logger.info("Camera resources released during shutdown.")

    @property
    def is_running(self) -> bool:
        """Return whether the managed OpenCV capture is currently open."""
        return self._capture is not None and self._capture.isOpened()

    def status(self) -> dict[str, bool | int]:
        """Return camera connection and capture status."""
        return {
            "connected": self.is_running or self._last_known_connected,
            "running": self.is_running,
            "camera_index": self._index,
        }

    def _release_capture(self) -> None:
        """Release the managed OpenCV capture instance if it exists."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None
