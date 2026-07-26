"""Debug visualization overlay for eye-tracking frames."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

import cv2
import numpy as np

from backend.eye_tracking.action_engine import ActionState, ActionType
from backend.eye_tracking.blink_detection_service import BlinkState
from backend.eye_tracking.calibration import CalibrationProgress
from backend.eye_tracking.cursor_controller import CursorControllerState
from backend.eye_tracking.gaze_service import GazeEstimate
from backend.eye_tracking.gesture_interpreter_service import GestureState, GestureType


@dataclass(frozen=True)
class DebugOverlayData:
    """Frame-local debug values for the accessibility overlay."""

    gaze_estimate: GazeEstimate | None
    calibration_progress: CalibrationProgress
    blink_state: BlinkState | None
    gesture_state: GestureState | None
    action_state: ActionState | None
    cursor_state: CursorControllerState | None
    tracking_confidence: float
    measured_fps: float
    face_detected: bool
    tracking_ok: bool


class GazeDebugVisualizationService:
    """Draw gaze and status debugging information onto camera frames."""

    def __init__(self, overlay_mode: str = "normal") -> None:
        """Create an overlay service in normal or debug mode."""
        if overlay_mode not in {"normal", "debug"}:
            raise ValueError("overlay_mode must be 'normal' or 'debug'.")
        self._mode = overlay_mode
        self._lock = RLock()

    def set_mode(self, mode: str) -> str:
        """Switch between ``normal`` and ``debug`` overlay modes."""
        if mode not in {"normal", "debug"}:
            raise ValueError("overlay_mode must be 'normal' or 'debug'.")
        with self._lock:
            self._mode = mode
            return self._mode

    def get_mode(self) -> str:
        """Return the active overlay mode."""
        with self._lock:
            return self._mode

    def draw_overlay(self, frame: np.ndarray, data: DebugOverlayData) -> np.ndarray:
        """Return ``frame`` with gaze and status debug overlays."""
        if data.gaze_estimate is not None and data.tracking_ok:
            self._draw_gaze_point(frame, data.gaze_estimate)

        self._draw_blink_hold_indicator(frame, data.blink_state)

        with self._lock:
            mode = self._mode

        lines = (
            self._normal_lines(data)
            if mode == "normal"
            else self._debug_lines(data)
        )
        self._draw_lines(frame, lines)
        return frame

    def _normal_lines(self, data: DebugOverlayData) -> tuple[str, ...]:
        """Compact demo-facing status lines."""
        tracking_status = "Active" if data.tracking_ok else "Tracking Lost"
        calibration = data.calibration_progress
        if calibration.complete:
            quality = calibration.quality
            if quality is not None and quality.recommend_recalibration:
                calibration_status = "Recalibration Recommended"
            else:
                calibration_status = "Complete"
        elif calibration.completed_points > 0:
            calibration_status = (
                f"In Progress ({calibration.completed_points}/{calibration.total_points})"
            )
        else:
            calibration_status = "Not Started"

        cursor_enabled = (
            "Yes" if data.cursor_state is not None and data.cursor_state.enabled else "No"
        )
        gesture = (
            data.gesture_state.gesture.value
            if data.gesture_state is not None
            else GestureType.NO_GESTURE.value
        )
        action = (
            data.action_state.action.value
            if data.action_state is not None
            else ActionType.NO_ACTION.value
        )
        return (
            f"Tracking Status: {tracking_status}",
            f"Calibration Status: {calibration_status}",
            f"Cursor Enabled: {cursor_enabled}",
            f"Blink Hold: {self._format_hold_progress(data.blink_state)}",
            f"Current Gesture: {gesture}",
            f"Current Action: {action}",
        )

    def _debug_lines(self, data: DebugOverlayData) -> tuple[str, ...]:
        """Developer diagnostics for EAR, confidence, and frame counters."""
        blink = data.blink_state
        quality = data.calibration_progress.quality
        quality_text = (
            f"{quality.label} ({quality.score:.2f})"
            if quality is not None
            else "n/a"
        )
        if quality is not None and quality.recommend_recalibration:
            quality_text += " — recalibrate"

        cursor = data.cursor_state
        cursor_x = (
            str(cursor.lastX)
            if cursor is not None and cursor.lastX is not None
            else "--"
        )
        cursor_y = (
            str(cursor.lastY)
            if cursor is not None and cursor.lastY is not None
            else "--"
        )
        gesture = (
            data.gesture_state.gesture.value
            if data.gesture_state is not None
            else GestureType.NO_GESTURE.value
        )
        action = (
            data.action_state.action.value
            if data.action_state is not None
            else ActionType.NO_ACTION.value
        )
        tracking_status = "Active" if data.tracking_ok else "Tracking Lost"

        return (
            f"Tracking Status: {tracking_status}",
            f"FPS: {data.measured_fps:.1f}",
            f"Left EAR: {self._format_ear(blink.leftEar if blink else None)}",
            f"Right EAR: {self._format_ear(blink.rightEar if blink else None)}",
            f"Smoothed EAR: {self._format_ear(blink.smoothedEar if blink else None)}",
            f"Tracking Confidence: {data.tracking_confidence:.2f}",
            f"Calibration Quality: {quality_text}",
            f"Blink Hold: {self._format_hold_progress(blink)}",
            f"Closed Frames: {blink.closedFrames if blink else 0}",
            f"Open Frames: {blink.openFrames if blink else 0}",
            f"Cursor Position: ({cursor_x}, {cursor_y})",
            f"Current Gesture: {gesture}",
            f"Current Action: {action}",
        )

    def _draw_blink_hold_indicator(
        self,
        frame: np.ndarray,
        blink_state: BlinkState | None,
    ) -> None:
        """Draw a circular progress ring while an intentional blink is held."""
        if blink_state is None or not blink_state.holdActive:
            return

        height, width = frame.shape[:2]
        center = (width // 2, max(int(height * 0.18), 48))
        radius = max(int(min(width, height) * 0.07), 28)
        progress = min(max(float(blink_state.holdProgress), 0.0), 1.0)

        cv2.circle(frame, center, radius, (40, 40, 40), 4, lineType=cv2.LINE_AA)
        if progress > 0.0:
            # OpenCV ellipses use 0° at 3 o'clock; start at 12 o'clock (-90°).
            end_angle = -90.0 + (360.0 * progress)
            color = (0, 220, 0) if progress >= 1.0 else (0, 200, 255)
            cv2.ellipse(
                frame,
                center,
                (radius, radius),
                0,
                -90.0,
                end_angle,
                color,
                4,
                lineType=cv2.LINE_AA,
            )

        label = "CLICK" if progress >= 1.0 else f"{int(progress * 100)}%"
        text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)[0]
        text_origin = (
            center[0] - text_size[0] // 2,
            center[1] + text_size[1] // 2,
        )
        cv2.putText(
            frame,
            label,
            text_origin,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 0),
            3,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            label,
            text_origin,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    def _format_hold_progress(self, blink_state: BlinkState | None) -> str:
        """Format blink-hold progress for overlay text."""
        if blink_state is None or not blink_state.holdActive:
            return "Idle"
        percent = int(round(min(max(blink_state.holdProgress, 0.0), 1.0) * 100))
        if blink_state.holdProgress >= 1.0:
            return f"{percent}% — click"
        return f"{percent}% ({blink_state.holdDurationMs:.0f} ms)"

    def _draw_gaze_point(self, frame: np.ndarray, gaze_estimate: GazeEstimate) -> None:
        """Draw the normalized gaze point scaled into frame coordinates."""
        height, width = frame.shape[:2]
        x = self._normalized_to_pixel(gaze_estimate.x, width)
        y = self._normalized_to_pixel(gaze_estimate.y, height)
        cv2.circle(frame, (x, y), radius=8, color=(0, 0, 255), thickness=-1)
        cv2.circle(frame, (x, y), radius=12, color=(255, 255, 255), thickness=2)

    def _draw_lines(self, frame: np.ndarray, lines: tuple[str, ...]) -> None:
        """Render status text with a high-contrast outline."""
        x = 12
        y = 24
        line_height = 22
        for index, line in enumerate(lines):
            origin = (x, y + index * line_height)
            cv2.putText(
                frame,
                line,
                origin,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 0, 0),
                4,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                line,
                origin,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

    def _format_ear(self, value: float | None) -> str:
        """Format an EAR value for overlay text."""
        if value is None:
            return "--"
        return f"{value:.3f}"

    def _normalized_to_pixel(self, value: float, size: int) -> int:
        """Scale a normalized coordinate into a bounded pixel coordinate."""
        if size <= 1:
            return 0
        normalized = min(max(float(value), 0.0), 1.0)
        return min(max(int(round(normalized * (size - 1))), 0), size - 1)
