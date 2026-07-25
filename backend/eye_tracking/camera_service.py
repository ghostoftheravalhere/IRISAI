"""Camera service for managing the OpenCV webcam capture lifecycle."""

from collections.abc import Iterator
from threading import RLock

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
        self._lock = RLock()

    def start(self) -> dict[str, bool | int]:
        """Start the webcam capture and return the latest camera status.

        Raises:
            CameraServiceError: If the camera is already running or cannot be
                opened by OpenCV.
        """
        with self._lock:
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
        with self._lock:
            if not self.is_running:
                message = f"Camera index {self._index} is not running."
                logger.warning(message)
                raise CameraServiceError(message, status_code=409)

            self._release_capture()
            logger.info("Camera stopped on index %d", self._index)
            return self.status()

    def cleanup(self) -> None:
        """Release camera resources during application shutdown."""
        with self._lock:
            if self._capture is not None:
                self._release_capture()
                logger.info("Camera resources released during shutdown.")

    def mjpeg_frame_stream(self) -> Iterator[bytes]:
        """Yield JPEG-encoded frames for an MJPEG HTTP stream.

        The stream reads only from the existing running capture. It exits when
        the camera stops, the camera disconnects, frame encoding fails, or the
        HTTP client disconnects.

        """
        if not self.is_running:
            message = f"Camera index {self._index} is not running."
            logger.warning("Camera stream closed before first frame: %s", message)
            return

        logger.info("Camera MJPEG stream opened for index %d", self._index)
        try:
            while self.is_running:
                frame = self._read_jpeg_frame()
                if frame is None:
                    break

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    + f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii")
                    + frame
                    + b"\r\n"
                )
        finally:
            logger.info("Camera MJPEG stream closed for index %d", self._index)

    @property
    def is_running(self) -> bool:
        """Return whether the managed OpenCV capture is currently open."""
        with self._lock:
            return self._capture is not None and self._capture.isOpened()

    def status(self) -> dict[str, bool | int]:
        """Return camera connection and capture status."""
        with self._lock:
            running = self.is_running
            return {
                "connected": running or self._last_known_connected,
                "running": running,
                "camera_index": self._index,
            }

    def _read_jpeg_frame(self) -> bytes | None:
        """Read one frame from the active capture and encode it as JPEG."""
        with self._lock:
            if not self.is_running or self._capture is None:
                return None

            success, frame = self._capture.read()

        if not success or frame is None:
            logger.warning("Camera frame read failed on index %d.", self._index)
            self._handle_disconnected_camera()
            return None

        encoded, buffer = cv2.imencode(".jpg", frame)
        if not encoded:
            logger.error("Camera frame JPEG encoding failed on index %d.", self._index)
            return None

        return buffer.tobytes()

    def _handle_disconnected_camera(self) -> None:
        """Mark the camera disconnected and release the failed capture."""
        with self._lock:
            self._last_known_connected = False
            self._release_capture()

    def _release_capture(self) -> None:
        """Release the managed OpenCV capture instance if it exists."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None
