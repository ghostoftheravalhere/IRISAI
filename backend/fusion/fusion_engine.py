"""Multimodal Gaze-Voice Fusion Engine for IRIS AI.

Correlates real-time gaze fixations with spoken commands to execute native
Win32 OS actions at precise target coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import threading
import time
from typing import Any, Callable

from backend.eye_tracking.cursor_controller import CursorController
from backend.services.system_cursor import SystemCursor, system_cursor
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class GazeAnchor:
    """Snapshot of coordinates at the moment voice input began."""

    x: int
    y: int
    timestamp: float = field(default_factory=time.time)

    def is_valid(self, max_drift_seconds: float = 2.0, now: float | None = None) -> bool:
        """Check if snapshot is still fresh within the maximum drift window."""
        current_time = now if now is not None else time.time()
        return (current_time - self.timestamp) <= max_drift_seconds


@dataclass(frozen=True)
class FusionActionResponse:
    """Execution result of a multimodal gaze-voice action."""

    success: bool
    action: str
    target_x: int
    target_y: int
    used_anchor: bool
    message: str


class GazeVoiceFusionEngine:
    """Multimodal Gaze-Voice Fusion Engine for IRIS AI.

    Tracks gaze coordinates when speech starts (VAD / PTT activation)
    and dispatches native Win32 pointer actions ("click", "open", "double click",
    "right click", "drag", "drop") directly to the anchored coordinates.
    """

    def __init__(
        self,
        cursor_controller: CursorController | None = None,
        system_cursor_service: SystemCursor | None = None,
        max_drift_seconds: float = 2.0,
    ) -> None:
        self._cursor_controller = cursor_controller
        self._system_cursor = system_cursor_service or system_cursor
        self._max_drift_seconds = max_drift_seconds
        self._latest_anchor: GazeAnchor | None = None
        self._last_action_response: FusionActionResponse | None = None
        self._lock = threading.RLock()
        self._listeners: list[Callable[[FusionActionResponse], None]] = []

    @property
    def max_drift_seconds(self) -> float:
        return self._max_drift_seconds

    @max_drift_seconds.setter
    def max_drift_seconds(self, value: float) -> None:
        with self._lock:
            self._max_drift_seconds = max(0.1, float(value))

    def set_cursor_controller(self, controller: CursorController) -> None:
        """Attach active cursor controller instance."""
        with self._lock:
            self._cursor_controller = controller

    def add_listener(self, callback: Callable[[FusionActionResponse], None]) -> None:
        """Add a listener callback for fusion actions."""
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[FusionActionResponse], None]) -> None:
        """Remove a listener callback."""
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def anchor_gaze(
        self,
        x: int | None = None,
        y: int | None = None,
        timestamp: float | None = None,
    ) -> GazeAnchor:
        """Capture and record the current gaze/cursor coordinates as the anchor point."""
        ts = timestamp if timestamp is not None else time.time()
        with self._lock:
            if x is not None and y is not None:
                anchor_x, anchor_y = int(x), int(y)
            elif self._cursor_controller is not None:
                try:
                    anchor_x, anchor_y = self._cursor_controller.get_current_position()
                except Exception as e:
                    logger.warning("[FUSION] Failed to query cursor_controller position: %s", e)
                    anchor_x, anchor_y = self._system_cursor.get_cursor_position()
            else:
                anchor_x, anchor_y = self._system_cursor.get_cursor_position()

            self._latest_anchor = GazeAnchor(x=anchor_x, y=anchor_y, timestamp=ts)
            logger.info(
                "[FUSION] Gaze anchored at (%d, %d) at timestamp %.3f",
                anchor_x,
                anchor_y,
                ts,
            )
            return self._latest_anchor

    def handle_speech_start(self) -> GazeAnchor:
        """VAD / Speech onset trigger hook."""
        return self.anchor_gaze()

    def get_latest_anchor(self) -> GazeAnchor | None:
        """Return the latest recorded gaze anchor if any."""
        with self._lock:
            return self._latest_anchor

    def clear_anchor(self) -> None:
        """Clear the current gaze anchor."""
        with self._lock:
            self._latest_anchor = None

    def resolve_target_coordinates(
        self,
        now: float | None = None,
    ) -> tuple[int, int, bool]:
        """Resolve coordinates for an action: use valid anchor or fallback to live cursor."""
        current_time = now if now is not None else time.time()
        with self._lock:
            if self._latest_anchor is not None and self._latest_anchor.is_valid(
                self._max_drift_seconds, now=current_time
            ):
                logger.info("[FUSION] Using valid gaze anchor at (%d, %d)", self._latest_anchor.x, self._latest_anchor.y)
                return self._latest_anchor.x, self._latest_anchor.y, True

            # Fallback to current live cursor position (works universally whether gaze control is ON or OFF)
            try:
                if self._cursor_controller is not None:
                    live_x, live_y = self._cursor_controller.get_current_position()
                else:
                    live_x, live_y = self._system_cursor.get_cursor_position()
            except Exception as exc:
                logger.debug("[FUSION] Failed getting cursor_controller position (%s); using system_cursor: %s", exc)
                live_x, live_y = self._system_cursor.get_cursor_position()
            logger.info("[FUSION] Anchor expired or missing. Fallback to live cursor position at (%d, %d)", live_x, live_y)
            return live_x, live_y, False

    def process_voice_command(
        self,
        command_text: str,
        timestamp: float | None = None,
    ) -> FusionActionResponse | None:
        """Parse voice utterance and dispatch gaze-anchored native Win32 action."""
        import re

        raw_text = str(command_text or "").strip()
        clean_text = re.sub(r"[^\w\s]", "", raw_text).lower().strip()
        if not clean_text:
            return None

        # Priority 1: Multi-word specific clicks or 'open' gaze target
        if clean_text == "open" or any(w in clean_text for w in ("double click", "double-click", "doubleclick", "do a double click", "open this", "open file", "open item", "open folder")):
            return self.execute_action("DOUBLE_CLICK", timestamp=timestamp)
        if any(w in clean_text for w in ("right click", "right-click", "rightclick", "do a right click", "context menu", "open menu", "menu")):
            return self.execute_action("RIGHT_CLICK", timestamp=timestamp)
        if any(w in clean_text for w in ("drag", "hold", "grab", "start selecting", "begin selection")):
            return self.execute_action("MOUSE_DOWN", timestamp=timestamp)
        if any(w in clean_text for w in ("drop", "release", "let go", "stop selecting", "end selection")):
            return self.execute_action("MOUSE_UP", timestamp=timestamp)
        if any(w in clean_text for w in ("click", "select", "tap", "left click", "left-click", "single click", "press")) or clean_text == "click":
            return self.execute_action("LEFT_CLICK", timestamp=timestamp)

        return None

    def execute_action(
        self,
        action: str,
        timestamp: float | None = None,
    ) -> FusionActionResponse:
        """Execute the specified action at resolved target coordinates."""
        now = timestamp if timestamp is not None else time.time()
        target_x, target_y, used_anchor = self.resolve_target_coordinates(now=now)

        success = False
        action_name = action.upper().strip()

        # Execute native Win32 action via system_cursor (force=True so voice commands work whether gaze control is ON or OFF)
        if action_name == "LEFT_CLICK":
            success = self._system_cursor.click(target_x, target_y, button="left", force=True)
            try:
                from backend.eye_tracking.click_feedback_overlay import show_click_feedback_popup
                show_click_feedback_popup(text="Voice Click", duration_ms=900, x=target_x, y=target_y)
            except Exception:
                pass
        elif action_name == "DOUBLE_CLICK":
            success = self._system_cursor.double_click(target_x, target_y, button="left", force=True)
            try:
                from backend.eye_tracking.click_feedback_overlay import show_click_feedback_popup
                show_click_feedback_popup(text="Voice Double Click", duration_ms=900, x=target_x, y=target_y)
            except Exception:
                pass
        elif action_name == "RIGHT_CLICK":
            success = self._system_cursor.click(target_x, target_y, button="right", force=True)
            try:
                from backend.eye_tracking.click_feedback_overlay import show_click_feedback_popup
                show_click_feedback_popup(text="Voice Right Click", duration_ms=900, x=target_x, y=target_y)
            except Exception:
                pass
        elif action_name == "MOUSE_DOWN":
            success = self._system_cursor.mouse_down(target_x, target_y, button="left", force=True)
            try:
                from backend.eye_tracking.click_feedback_overlay import show_click_feedback_popup
                show_click_feedback_popup(text="Voice Drag Start", duration_ms=900, x=target_x, y=target_y)
            except Exception:
                pass
        elif action_name == "MOUSE_UP":
            success = self._system_cursor.mouse_up(target_x, target_y, button="left", force=True)
            try:
                from backend.eye_tracking.click_feedback_overlay import show_click_feedback_popup
                show_click_feedback_popup(text="Voice Drop", duration_ms=900, x=target_x, y=target_y)
            except Exception:
                pass
        else:
            return FusionActionResponse(
                success=False,
                action=action_name,
                target_x=target_x,
                target_y=target_y,
                used_anchor=used_anchor,
                message=f"Unsupported fusion action: {action_name}",
            )

        resp = FusionActionResponse(
            success=success,
            action=action_name,
            target_x=target_x,
            target_y=target_y,
            used_anchor=used_anchor,
            message=f"Executed {action_name} at ({target_x}, {target_y}) (anchored={used_anchor})",
        )

        with self._lock:
            self._last_action_response = resp
            listeners = list(self._listeners)

        for listener in listeners:
            try:
                listener(resp)
            except Exception:
                logger.exception("Error in fusion action listener callback")

        # After a discrete click or drop, clear anchor so subsequent actions re-sample
        if action_name in ("LEFT_CLICK", "DOUBLE_CLICK", "RIGHT_CLICK", "MOUSE_UP"):
            self.clear_anchor()

        return resp

    def get_status(self) -> dict[str, Any]:
        """Return operational telemetry for APIs and monitoring UI."""
        with self._lock:
            anchor_info = None
            if self._latest_anchor is not None:
                anchor_info = {
                    "x": self._latest_anchor.x,
                    "y": self._latest_anchor.y,
                    "timestamp": self._latest_anchor.timestamp,
                    "is_valid": self._latest_anchor.is_valid(self._max_drift_seconds),
                }
            last_resp = None
            if self._last_action_response is not None:
                last_resp = {
                    "success": self._last_action_response.success,
                    "action": self._last_action_response.action,
                    "target_x": self._last_action_response.target_x,
                    "target_y": self._last_action_response.target_y,
                    "used_anchor": self._last_action_response.used_anchor,
                    "message": self._last_action_response.message,
                }

            return {
                "max_drift_seconds": self._max_drift_seconds,
                "latest_anchor": anchor_info,
                "last_action": last_resp,
                "cursor_enabled": self._system_cursor.enabled,
            }


# Global singleton instance
gaze_voice_fusion = GazeVoiceFusionEngine()
