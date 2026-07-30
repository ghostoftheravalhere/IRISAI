"""Camera service for managing the OpenCV webcam capture lifecycle."""

from __future__ import annotations

from collections.abc import Iterator
from threading import Event, RLock, Thread
from time import sleep
from typing import TYPE_CHECKING

import cv2
import numpy as np

from backend.eye_tracking.face_mesh_service import EyeData, FaceMeshService
from backend.utils.helpers import compute_eye_center
from backend.utils.logger import get_logger

if TYPE_CHECKING:
    from backend.eye_tracking.action_engine import ActionState
    from backend.eye_tracking.action_engine import ActionEngine
    from backend.eye_tracking.blink_detection_service import BlinkDetectionService
    from backend.eye_tracking.blink_detection_service import BlinkState
    from backend.eye_tracking.calibration import EyeCalibrationService
    from backend.eye_tracking.cursor_controller import CursorControllerState
    from backend.eye_tracking.cursor_controller import CursorController
    from backend.eye_tracking.debug_visualization_service import GazeDebugVisualizationService
    from backend.eye_tracking.eye_interaction_config import EyeInteractionConfig
    from backend.eye_tracking.gaze_service import GazeEstimate
    from backend.eye_tracking.gesture_interpreter_service import GestureInterpreterService
    from backend.eye_tracking.gaze_service import EyeGazeService

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

    def __init__(
        self,
        camera_index: int = 0,
        eye_config: EyeInteractionConfig | None = None,
    ) -> None:
        """Create a camera service for the configured OpenCV camera index."""
        from backend.eye_tracking.eye_interaction_config import default_eye_interaction_config

        self._index = camera_index
        self._eye_config = eye_config or default_eye_interaction_config()
        self._capture: cv2.VideoCapture | None = None
        self._face_mesh = FaceMeshService()
        self._latest_eye_data: EyeData | None = None
        self._gaze_service: EyeGazeService | None = None
        self._calibration_service: EyeCalibrationService | None = None
        self._debug_visualizer: GazeDebugVisualizationService | None = None
        self._blink_detection_service: BlinkDetectionService | None = None
        self._gesture_interpreter_service: GestureInterpreterService | None = None
        self._action_engine: ActionEngine | None = None
        self._cursor_controller: CursorController | None = None
        self._last_known_connected = False
        self._latest_jpeg: bytes | None = None
        self._processing_thread: Thread | None = None
        self._stop_event = Event()
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
            self._stop_event.clear()
            self._processing_thread = Thread(
                target=self._processing_loop,
                name=f"iris-camera-loop-{self._index}",
                daemon=True,
            )
            self._processing_thread.start()
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

        self._stop_processing_loop()
        self.reset_interaction_pipeline()
        with self._lock:
            self._release_capture()
            self._latest_jpeg = None
            self._latest_eye_data = None
            logger.info("Camera stopped on index %d", self._index)
            return self.status()

    def cleanup(self) -> None:
        """Release camera resources during application shutdown."""
        self._stop_processing_loop()
        self.reset_interaction_pipeline()
        with self._lock:
            if self._capture is not None:
                self._release_capture()
                self._latest_jpeg = None
                self._latest_eye_data = None
                logger.info("Camera resources released during shutdown.")
            self._face_mesh.close()

    def reset_interaction_pipeline(self) -> None:
        """Disable cursor and reset blink/gesture/action/gaze interaction state."""
        with self._lock:
            cursor_controller = self._cursor_controller
            blink_detection_service = self._blink_detection_service
            gesture_interpreter_service = self._gesture_interpreter_service
            action_engine = self._action_engine
            gaze_service = self._gaze_service

        if cursor_controller is not None:
            cursor_controller.disable()
        if blink_detection_service is not None:
            blink_detection_service.reset()
        if gesture_interpreter_service is not None:
            gesture_interpreter_service.reset()
        if action_engine is not None:
            action_engine.reset()
        if gaze_service is not None:
            gaze_service.reset()

    def mjpeg_frame_stream(self) -> Iterator[bytes]:
        """Yield the latest processed JPEG frames for an MJPEG HTTP stream.

        Frame capture and eye-tracking run on a background loop. This endpoint
        only publishes the most recent encoded frame and does not drive processing.
        """
        if not self.is_running:
            message = f"Camera index {self._index} is not running."
            logger.warning("Camera stream closed before first frame: %s", message)
            return

        logger.info("Camera MJPEG stream opened for index %d", self._index)
        try:
            while self.is_running and not self._stop_event.is_set():
                with self._lock:
                    frame = self._latest_jpeg
                if frame is None:
                    sleep(0.02)
                    continue

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    + f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii")
                    + frame
                    + b"\r\n"
                )
                sleep(0.033)
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

    def get_latest_eye_data(self) -> EyeData | None:
        """Return the latest normalized eye landmark data, if available."""
        with self._lock:
            return self._latest_eye_data

    def collect_calibration_eye_samples(
        self,
        *,
        sample_count: int | None = None,
        stabilize_ms: float | None = None,
        timeout_ms: float | None = None,
        poll_interval_ms: float | None = None,
    ) -> list[EyeData]:
        """Collect consecutive eye landmark samples from the background loop.

        Performs a short stabilization wait, then polls ``get_latest_eye_data``
        so calibration never contends with the processing thread for ``read()``.
        """
        from time import monotonic

        count = (
            self._eye_config.calibration_sample_count
            if sample_count is None
            else sample_count
        )
        settle_ms = (
            self._eye_config.calibration_stabilize_ms
            if stabilize_ms is None
            else stabilize_ms
        )
        max_ms = (
            self._eye_config.calibration_sample_timeout_ms
            if timeout_ms is None
            else timeout_ms
        )
        poll_ms = (
            self._eye_config.calibration_sample_poll_ms
            if poll_interval_ms is None
            else poll_interval_ms
        )

        if count < 1:
            raise ValueError("sample_count must be at least 1.")
        if not self.is_running:
            raise CameraServiceError("Camera is not running.", status_code=409)

        settle_s = max(settle_ms, 0.0) / 1000.0
        timeout_s = max(max_ms, 0.0) / 1000.0
        poll_s = max(poll_ms, 1.0) / 1000.0

        settle_deadline = monotonic() + settle_s
        while monotonic() < settle_deadline:
            sleep(poll_s)

        samples: list[EyeData] = []
        collect_deadline = monotonic() + timeout_s
        previous_center: tuple[float, float] | None = None
        while len(samples) < count and monotonic() < collect_deadline:
            eye_data = self.get_latest_eye_data()
            if eye_data is None:
                sleep(poll_s)
                continue

            # Sprint 1: shared helper removes duplicate eye-center averaging logic.
            center = compute_eye_center(eye_data)
            if center is None:
                sleep(poll_s)
                continue

            # Skip near-duplicate frames from camera buffering.
            if previous_center is not None:
                dx = center[0] - previous_center[0]
                dy = center[1] - previous_center[1]
                if (dx * dx + dy * dy) < 1e-12:
                    sleep(poll_s)
                    continue

            samples.append(eye_data)
            previous_center = center
            sleep(poll_s)

        logger.info(
            "Collected %d/%d calibration eye frames (stabilize=%.0fms timeout=%.0fms).",
            len(samples),
            count,
            settle_ms,
            max_ms,
        )
        return samples

    def _stop_processing_loop(self) -> None:
        """Signal and join the background capture/processing thread."""
        self._stop_event.set()
        thread = self._processing_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self._processing_thread = None

    def _processing_loop(self) -> None:
        """Continuously capture and process frames for eye tracking."""
        logger.info("Camera processing loop started on index %d.", self._index)
        try:
            while not self._stop_event.is_set():
                with self._lock:
                    capture = self._capture
                    if capture is None or not capture.isOpened():
                        break
                    success, frame = capture.read()

                if not success or frame is None:
                    logger.warning("Camera frame read failed on index %d.", self._index)
                    self._handle_disconnected_camera()
                    break

                processed = self._process_frame(frame)
                encoded, buffer = cv2.imencode(".jpg", processed)
                if not encoded:
                    logger.error(
                        "Camera frame JPEG encoding failed on index %d.", self._index
                    )
                    continue

                with self._lock:
                    self._latest_jpeg = buffer.tobytes()
        finally:
            logger.info("Camera processing loop stopped on index %d.", self._index)

    def configure_gaze_debug_visualization(
        self,
        gaze_service: EyeGazeService,
        calibration_service: EyeCalibrationService,
        debug_visualizer: GazeDebugVisualizationService,
    ) -> None:
        """Attach optional gaze debug visualization services."""
        with self._lock:
            self._gaze_service = gaze_service
            self._calibration_service = calibration_service
            self._debug_visualizer = debug_visualizer

    def configure_blink_detection(
        self,
        blink_detection_service: BlinkDetectionService,
        gesture_interpreter_service: GestureInterpreterService | None = None,
        action_engine: ActionEngine | None = None,
        cursor_controller: CursorController | None = None,
    ) -> None:
        """Attach optional blink, gesture, action, and cursor services."""
        with self._lock:
            self._blink_detection_service = blink_detection_service
            self._gesture_interpreter_service = gesture_interpreter_service
            self._action_engine = action_engine
            self._cursor_controller = cursor_controller

    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Apply face mesh, blink/gesture/cursor pipeline, and debug overlay."""
        try:
            result = self._face_mesh.process_frame(frame)
            face_detected = result.eye_data is not None
            with self._lock:
                self._latest_eye_data = result.eye_data

            gaze_estimate = self._estimate_gaze()
            tracking_confidence = (
                gaze_estimate.confidence if gaze_estimate is not None else 0.0
            )
            if not face_detected:
                tracking_confidence = 0.0

            # Cursor / overlay validity depends on gaze confidence.
            tracking_ok = (
                face_detected
                and tracking_confidence >= self._eye_config.tracking_confidence_threshold
            )
            # Blink/gesture validity depends only on face + eye landmarks.
            landmarks_ok = face_detected and result.eye_data is not None

            blink_state, action_state = self._update_blink_pipeline(
                eye_data=result.eye_data,
                landmarks_ok=landmarks_ok,
            )
            cursor_state = self._update_cursor(
                action_state=action_state,
                tracking_confidence=tracking_confidence,
                face_detected=face_detected,
            )
            return self._draw_debug_overlay(
                frame=result.frame,
                gaze_estimate=gaze_estimate,
                blink_state=blink_state,
                action_state=action_state,
                cursor_state=cursor_state,
                tracking_confidence=tracking_confidence,
                face_detected=face_detected,
                tracking_ok=tracking_ok,
            )
        except Exception:
            logger.exception("Camera frame processing failed; streaming raw frame.")
            with self._lock:
                self._latest_eye_data = None
            blink_state, action_state = self._update_blink_pipeline(
                eye_data=None,
                landmarks_ok=False,
            )
            self._update_cursor(
                action_state=action_state,
                tracking_confidence=0.0,
                face_detected=False,
            )
            return frame

    def _estimate_gaze(self) -> GazeEstimate | None:
        """Estimate gaze from the latest eye data when configured."""
        with self._lock:
            gaze_service = self._gaze_service

        if gaze_service is None:
            return None

        try:
            return gaze_service.estimate_latest_gaze()
        except Exception:
            logger.exception("Gaze estimation failed.")
            return None

    def _update_blink_pipeline(
        self,
        eye_data: EyeData | None,
        landmarks_ok: bool,
    ) -> tuple[BlinkState | None, ActionState | None]:
        """Update blink → gesture → action and return intermediate blink state.

        Blink detection and intentional gestures run whenever valid eye landmarks
        are present. Gaze confidence only freezes cursor movement, not blinks.
        """
        with self._lock:
            blink_detection_service = self._blink_detection_service

        if blink_detection_service is None:
            return None, None

        try:
            blink_state = blink_detection_service.update(eye_data)
        except Exception:
            logger.exception("Blink detection update failed.")
            return None, None

        with self._lock:
            gesture_interpreter_service = self._gesture_interpreter_service

        if gesture_interpreter_service is None:
            return blink_state, None

        try:
            gesture_state = gesture_interpreter_service.update(blink_state)
        except Exception:
            logger.exception("Gesture interpretation update failed.")
            return blink_state, None

        with self._lock:
            action_engine = self._action_engine

        if action_engine is None:
            return blink_state, None

        try:
            if not landmarks_ok:
                # Face/landmarks lost: freeze click execution only.
                return blink_state, action_engine.update(None)
            return blink_state, action_engine.update(gesture_state)
        except Exception:
            logger.exception("Action update failed.")
            return blink_state, None

    def _update_cursor(
        self,
        action_state: ActionState | None,
        tracking_confidence: float = 1.0,
        face_detected: bool = True,
    ) -> CursorControllerState | None:
        """Update cursor movement from latest gaze and action state when configured."""
        with self._lock:
            cursor_controller = self._cursor_controller

        if cursor_controller is None:
            return None

        try:
            return cursor_controller.update(
                action_state=action_state,
                tracking_confidence=tracking_confidence,
                face_detected=face_detected,
            )
        except Exception:
            logger.exception("Cursor update failed.")
            return cursor_controller.get_state()

    def _draw_debug_overlay(
        self,
        frame: np.ndarray,
        gaze_estimate: GazeEstimate | None,
        blink_state: BlinkState | None,
        action_state: ActionState | None,
        cursor_state: CursorControllerState | None,
        tracking_confidence: float,
        face_detected: bool,
        tracking_ok: bool,
    ) -> np.ndarray:
        """Draw gaze debug visualization when services are configured."""
        with self._lock:
            calibration_service = self._calibration_service
            debug_visualizer = self._debug_visualizer
            gesture_interpreter_service = self._gesture_interpreter_service

        if calibration_service is None or debug_visualizer is None:
            return frame

        try:
            from backend.eye_tracking.debug_visualization_service import DebugOverlayData

            calibration_progress = calibration_service.get_progress()
            gesture_state = (
                gesture_interpreter_service.get_latest_state()
                if gesture_interpreter_service is not None
                else None
            )
            measured_fps = blink_state.measuredFps if blink_state is not None else 0.0
            return debug_visualizer.draw_overlay(
                frame,
                DebugOverlayData(
                    gaze_estimate=gaze_estimate,
                    calibration_progress=calibration_progress,
                    blink_state=blink_state,
                    gesture_state=gesture_state,
                    action_state=action_state,
                    cursor_state=cursor_state,
                    tracking_confidence=tracking_confidence,
                    measured_fps=measured_fps,
                    face_detected=face_detected,
                    tracking_ok=tracking_ok,
                ),
            )
        except Exception:
            logger.exception("Gaze debug visualization failed; streaming frame without overlay.")
            return frame

    def _handle_disconnected_camera(self) -> None:
        """Mark the camera disconnected and release the failed capture."""
        self._stop_event.set()
        with self._lock:
            self._last_known_connected = False
            self._release_capture()
            self._latest_jpeg = None
            self._latest_eye_data = None
        self.reset_interaction_pipeline()

    def _release_capture(self) -> None:
        """Release the managed OpenCV capture instance if it exists."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None
