"""OS cursor control from normalized eye gaze."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import hypot, isfinite
from threading import RLock
from typing import Any

from backend.eye_tracking.action_engine import ActionState, ActionType
from backend.eye_tracking.eye_interaction_config import (
    EyeInteractionConfig,
    default_eye_interaction_config,
)
from backend.eye_tracking.gaze_service import EyeGazeService, GazeEstimate
from backend.services.system_cursor import system_cursor
from backend.vision.kalman_filter import GazeKalmanFilter
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class CursorControllerConfig:
    """Configurable cursor movement behavior."""

    sensitivity: float = 0.92
    smoothing_alpha: float = 0.20
    dead_zone_px: float = 15.0
    min_move_px: float = 2.5
    edge_padding_px: int = 8
    move_duration_seconds: float = 0.0
    tracking_confidence_threshold: float = 0.45
    max_step_px: float = 1200.0
    recovery_frames: int = 6
    history_buffer_maxlen: int = 10
    ear_freeze_threshold: float = 0.28


@dataclass(frozen=True)
class CursorControllerState:
    """Latest cursor controller state."""

    enabled: bool
    paused: bool
    dragMode: bool
    trackingActive: bool
    trackingConfidence: float
    lastX: int | None
    lastY: int | None


class CursorController:
    """Move the OS cursor using calibrated gaze when explicitly enabled.

    Movement pauses automatically when tracking confidence is low or the face
    is lost, which prevents accessibility-hostile cursor jitter.
    """

    def __init__(
        self,
        gaze_service: EyeGazeService,
        config: CursorControllerConfig | None = None,
        eye_config: EyeInteractionConfig | None = None,
    ) -> None:
        """Create a disabled cursor controller."""
        shared = eye_config or default_eye_interaction_config()
        shared.validate()
        self._gaze_service = gaze_service
        self._config = config or CursorControllerConfig(
            sensitivity=shared.cursor_sensitivity,
            smoothing_alpha=shared.cursor_smoothing_alpha,
            dead_zone_px=shared.cursor_dead_zone_px,
            min_move_px=shared.cursor_min_move_px,
            edge_padding_px=shared.cursor_edge_padding_px,
            move_duration_seconds=shared.cursor_move_duration_seconds,
            tracking_confidence_threshold=shared.tracking_confidence_threshold,
            max_step_px=shared.cursor_max_step_px,
            recovery_frames=shared.cursor_recovery_frames,
            history_buffer_maxlen=getattr(shared, "cursor_history_buffer_maxlen", 10),
            ear_freeze_threshold=getattr(shared, "ear_freeze_threshold", 0.28),
        )
        self._validate_config(self._config)
        self._pyautogui: Any | None = None
        self._enabled = False
        self._paused = False
        self._drag_mode = False
        self._drag_button_down = False
        self._tracking_active = False
        self._tracking_confidence = 0.0
        self._recovery_frames_remaining = 0
        self._last_x: int | None = None
        self._last_y: int | None = None
        self._smoothed_x: float | None = None
        self._smoothed_y: float | None = None
        self._last_action_timestamp: float | None = None
        self._last_executed_action_timestamp: float | None = None
        self._kalman_filter = GazeKalmanFilter()
        self.history_buffer: deque[tuple[int, int]] = deque(maxlen=self._config.history_buffer_maxlen)
        self._is_frozen_by_ear: bool = False
        self._lock = RLock()

    @property
    def kalman_filter(self) -> GazeKalmanFilter:
        """Return the internal 2D Kalman filter instance."""
        return self._kalman_filter

    def set_kalman_parameters(self, **kwargs) -> None:
        """Dynamically tune 2D Kalman filter parameters."""
        with self._lock:
            self._kalman_filter.set_parameters(**kwargs)

    def enable(self) -> CursorControllerState:
        """Enable cursor movement if PyAutoGUI or native SystemCursor is available."""
        with self._lock:
            if self._pyautogui is None:
                self._pyautogui = self._load_pyautogui()
            self._enabled = self._pyautogui is not None or system_cursor.enabled
            system_cursor.enabled = True
            if self._enabled:
                logger.info("Eye cursor controller enabled.")
            return self.get_state()

    def disable(self) -> CursorControllerState:
        """Disable cursor movement and release transient movement state."""
        with self._lock:
            self._release_drag_if_needed()
            self._enabled = False
            self._paused = False
            self._tracking_active = False
            self._tracking_confidence = 0.0
            system_cursor.enabled = False
            self._clear_motion_state()
            logger.info("Eye cursor controller disabled.")
            return self.get_state()

    def toggle(self) -> CursorControllerState:
        """Toggle cursor movement enablement."""
        with self._lock:
            if self._enabled:
                return self.disable()
            return self.enable()

    def update(
        self,
        action_state: ActionState | None = None,
        tracking_confidence: float | None = None,
        face_detected: bool = True,
        blink_state: Any | None = None,
    ) -> CursorControllerState:
        """Apply action state, check pre-blink EAR freeze gate, and move cursor."""
        with self._lock:
            if not self._enabled:
                self._tracking_active = False
                self._tracking_confidence = 0.0
                self._clear_motion_state()
                return self.get_state()

            # 1. Update Pre-Blink EAR Freeze Gate
            self._update_ear_freeze_state(blink_state)

            self._apply_action_state(action_state)
            confidence = self._resolve_confidence(tracking_confidence, face_detected)
            self._tracking_confidence = confidence

            if self._paused or not face_detected or confidence < self._config.tracking_confidence_threshold:
                was_active = self._tracking_active
                self._tracking_active = False
                self._clear_motion_state()
                self._release_drag_if_needed()
                if was_active:
                    self._recovery_frames_remaining = self._config.recovery_frames
                    logger.debug("cursor tracking frozen confidence=%.2f", confidence)
                return self.get_state()

            pyautogui = self._pyautogui

        if pyautogui is None:
            return self.disable()

        # 2. Execute pointer actions (using pre-blink coordinates from history buffer)
        self._execute_pointer_action(pyautogui, action_state)

        gaze = self._gaze_service.get_latest_gaze()
        if gaze is None:
            with self._lock:
                self._tracking_active = False
                self._tracking_confidence = 0.0
                self._clear_motion_state()
                self._release_drag_if_needed()
                return self.get_state()

        try:
            return self._move_toward_gaze(pyautogui, gaze)
        except Exception:
            logger.warning(
                "Transient eye cursor movement failed; preserving controller enabled state.",
                exc_info=True,
            )
            with self._lock:
                self._clear_motion_state()
            return self.get_state()

    def _extract_ear(self, blink_state: Any) -> float | None:
        """Extract scalar EAR value from blink state if available."""
        if blink_state is None:
            return None
        if isinstance(blink_state, (int, float)):
            val = float(blink_state)
            return val if isfinite(val) else None
        smoothed = getattr(blink_state, "smoothedEar", None)
        if smoothed is not None and isfinite(smoothed):
            return float(smoothed)
        left = getattr(blink_state, "leftEar", None)
        right = getattr(blink_state, "rightEar", None)
        if left is not None and right is not None and isfinite(left) and isfinite(right):
            return float((left + right) / 2.0)
        if left is not None and isfinite(left):
            return float(left)
        if right is not None and isfinite(right):
            return float(right)
        return None

    def _update_ear_freeze_state(self, blink_state: Any | None) -> None:
        """Update EAR pre-blink freeze gate state to eliminate blink drift."""
        if blink_state is None:
            return

        current_ear = self._extract_ear(blink_state)
        is_hold_active = bool(getattr(blink_state, "holdActive", False))
        is_eye_closing = bool(
            getattr(blink_state, "leftBlink", False)
            or getattr(blink_state, "rightBlink", False)
            or getattr(blink_state, "bothBlink", False)
            or not (getattr(blink_state, "leftEyeOpen", True) and getattr(blink_state, "rightEyeOpen", True))
        )

        if current_ear is not None and current_ear < self._config.ear_freeze_threshold:
            self._is_frozen_by_ear = True
        elif is_hold_active or is_eye_closing:
            self._is_frozen_by_ear = True
        elif (
            current_ear is not None
            and current_ear >= self._config.ear_freeze_threshold
            and getattr(blink_state, "leftEyeOpen", True)
            and getattr(blink_state, "rightEyeOpen", True)
            and not is_hold_active
        ):
            self._is_frozen_by_ear = False

    def get_current_position(self) -> tuple[int, int]:
        """Return current tracked cursor coordinates or live OS position."""
        with self._lock:
            if self._last_x is not None and self._last_y is not None:
                return (self._last_x, self._last_y)
        return system_cursor.get_cursor_position()

    def get_state(self) -> CursorControllerState:
        """Return the latest cursor controller state."""
        with self._lock:
            return CursorControllerState(
                enabled=self._enabled,
                paused=self._paused,
                dragMode=self._drag_mode,
                trackingActive=self._tracking_active,
                trackingConfidence=self._tracking_confidence,
                lastX=self._last_x,
                lastY=self._last_y,
            )

    def _resolve_confidence(
        self,
        tracking_confidence: float | None,
        face_detected: bool,
    ) -> float:
        """Combine explicit confidence with face-presence gating."""
        if not face_detected:
            return 0.0
        if tracking_confidence is None:
            return 1.0
        return min(max(float(tracking_confidence), 0.0), 1.0)

    def _move_toward_gaze(self, pyautogui: Any, gaze: GazeEstimate) -> CursorControllerState:
        """Smooth and clamp gaze into a cursor move, respecting the dead zone and EAR freeze gate."""
        if system_cursor.enabled:
            current_x_i, current_y_i = system_cursor.get_cursor_position()
            screen_width, screen_height = system_cursor.screen_size
        elif pyautogui is not None:
            screen_width, screen_height = pyautogui.size()
            current_x, current_y = pyautogui.position()
            current_x_i = int(current_x)
            current_y_i = int(current_y)
        else:
            current_x_i = self._last_x or 0
            current_y_i = self._last_y or 0
            screen_width, screen_height = 1920, 1080

        target_x, target_y = self._gaze_to_screen(
            gaze_x=gaze.x,
            gaze_y=gaze.y,
            screen_width=int(screen_width),
            screen_height=int(screen_height),
        )

        # Hold EMA while the raw target is still inside the dead zone so noise
        # cannot accumulate into a sudden jump later.
        with self._lock:
            reference_x = self._last_x if self._last_x is not None else current_x_i
            reference_y = self._last_y if self._last_y is not None else current_y_i
            raw_distance = hypot(target_x - reference_x, target_y - reference_y)
            if raw_distance < self._config.dead_zone_px:
                if self._smoothed_x is None or self._smoothed_y is None:
                    self._smoothed_x = float(reference_x)
                    self._smoothed_y = float(reference_y)
                self._tracking_active = True
                return self.get_state()

            # EAR Freeze Gate: if eyelid is closing or in hold active, freeze physical cursor
            if self._is_frozen_by_ear:
                self._tracking_active = True
                return self.get_state()

        next_x, next_y = self._smooth_target(
            target_x=target_x,
            target_y=target_y,
            current_x=current_x_i,
            current_y=current_y_i,
        )
        next_x, next_y = self._limit_step(
            next_x=next_x,
            next_y=next_y,
            current_x=current_x_i,
            current_y=current_y_i,
        )

        move_distance = hypot(next_x - current_x_i, next_y - current_y_i)
        if move_distance < self._config.min_move_px:
            with self._lock:
                self._tracking_active = True
                self.history_buffer.append((next_x, next_y))
                return self.get_state()

        if not hasattr(self, "_debug_cursor_frame_count"):
            self._debug_cursor_frame_count = 0
        self._debug_cursor_frame_count += 1
        if self._debug_cursor_frame_count % 30 == 0:
            print(
                f"[CURSOR DEBUG] Moving to: ({next_x}, {next_y}), raw gaze: ({gaze.x:.3f}, {gaze.y:.3f}), "
                f"conf={gaze.confidence:.2f}, sys_enabled={system_cursor.enabled}, ctrl_enabled={self._enabled}"
            )

        if system_cursor.enabled:
            system_cursor.move_cursor(next_x, next_y)
        elif pyautogui is not None:
            try:
                pyautogui.moveTo(
                    next_x,
                    next_y,
                    duration=self._config.move_duration_seconds,
                )
            except Exception:
                pass

        with self._lock:
            self._tracking_active = True
            self._last_x = next_x
            self._last_y = next_y
            self.history_buffer.append((next_x, next_y))
            return self.get_state()

    def _apply_action_state(self, action_state: ActionState | None) -> None:
        """Apply high-level action state to cursor controller state."""
        if action_state is None or action_state.timestamp is None:
            return
        if action_state.timestamp == self._last_action_timestamp:
            return

        self._last_action_timestamp = action_state.timestamp
        if action_state.action == ActionType.PAUSE_CURSOR:
            self._paused = True
            self._clear_motion_state()
            self._release_drag_if_needed()
        elif action_state.action == ActionType.RESUME_CURSOR:
            self._paused = False
            self._clear_motion_state()
        elif action_state.action == ActionType.TOGGLE_DRAG:
            self._drag_mode = action_state.dragMode

    def _execute_pointer_action(self, pyautogui: Any, action_state: ActionState | None) -> None:
        """Execute a pointer action using pre-blink history coordinates when cursor control is enabled."""
        if action_state is None or action_state.timestamp is None:
            return
        if action_state.timestamp != self._last_action_timestamp:
            return
        if action_state.timestamp == self._last_executed_action_timestamp:
            return

        # Pull retro-coordinates: oldest entry in history buffer (before eyelid began closing)
        with self._lock:
            if len(self.history_buffer) > 0:
                click_x, click_y = self.history_buffer[0]
            else:
                click_x, click_y = self._last_x, self._last_y

        try:
            if action_state.action == ActionType.LEFT_CLICK:
                if system_cursor.enabled:
                    system_cursor.click(click_x, click_y, button="left")
                else:
                    pyautogui.click(button="left")
                try:
                    from backend.eye_tracking.click_feedback_overlay import show_click_feedback_popup
                    show_click_feedback_popup(text="Left Click", duration_ms=900, x=click_x, y=click_y)
                except Exception:
                    pass
            elif action_state.action == ActionType.RIGHT_CLICK:
                if system_cursor.enabled:
                    system_cursor.click(click_x, click_y, button="right")
                else:
                    pyautogui.rightClick()
                try:
                    from backend.eye_tracking.click_feedback_overlay import show_click_feedback_popup
                    show_click_feedback_popup(text="Right Click", duration_ms=900, x=click_x, y=click_y)
                except Exception:
                    pass
            elif action_state.action == ActionType.DOUBLE_CLICK:
                if system_cursor.enabled:
                    system_cursor.click(click_x, click_y, button="left")
                    system_cursor.click(click_x, click_y, button="left")
                else:
                    pyautogui.doubleClick()
                try:
                    from backend.eye_tracking.click_feedback_overlay import show_click_feedback_popup
                    show_click_feedback_popup(text="Double Click", duration_ms=900, x=click_x, y=click_y)
                except Exception:
                    pass
            elif action_state.action == ActionType.TOGGLE_DRAG:
                self._sync_drag_button(pyautogui)
        except Exception:
            logger.exception("Pointer action execution failed.")
            return

        self._last_executed_action_timestamp = action_state.timestamp

    def _sync_drag_button(self, pyautogui: Any) -> None:
        """Synchronize physical drag button state with logical drag mode."""
        with self._lock:
            should_drag = self._drag_mode
            drag_button_down = self._drag_button_down

        if should_drag and not drag_button_down:
            pyautogui.mouseDown(button="left")
            with self._lock:
                self._drag_button_down = True
        elif not should_drag and drag_button_down:
            pyautogui.mouseUp(button="left")
            with self._lock:
                self._drag_button_down = False

    def _gaze_to_screen(
        self,
        gaze_x: float,
        gaze_y: float,
        screen_width: int,
        screen_height: int,
    ) -> tuple[int, int]:
        """Convert normalized gaze coordinates to clamped screen pixels."""
        if screen_width <= 0 or screen_height <= 0:
            raise ValueError("screen dimensions must be positive")

        x = self._apply_sensitivity(gaze_x)
        y = self._apply_sensitivity(gaze_y)
        max_x = max(screen_width - 1 - self._config.edge_padding_px, 0)
        max_y = max(screen_height - 1 - self._config.edge_padding_px, 0)
        min_x = min(self._config.edge_padding_px, max_x)
        min_y = min(self._config.edge_padding_px, max_y)

        return (
            min(max(int(round(x * (screen_width - 1))), min_x), max_x),
            min(max(int(round(y * (screen_height - 1))), min_y), max_y),
        )

    def _apply_sensitivity(self, value: float) -> float:
        """Scale normalized gaze around the center point."""
        if not isfinite(value):
            raise ValueError("gaze coordinate is not finite")

        scaled = 0.5 + (float(value) - 0.5) * self._config.sensitivity
        return min(max(scaled, 0.0), 1.0)

    def _smooth_target(
        self,
        target_x: int,
        target_y: int,
        current_x: int,
        current_y: int,
    ) -> tuple[int, int]:
        """Smooth cursor targets using 2D Kalman filter & adaptive anti-jitter pipeline."""
        with self._lock:
            if not self._kalman_filter.is_initialized:
                self._kalman_filter.update(float(target_x), float(target_y))
                self._smoothed_x = float(target_x)
                self._smoothed_y = float(target_y)
                return target_x, target_y

            if self._recovery_frames_remaining > 0:
                # Re-seed from the live OS cursor so recovery never teleports.
                seed_x = float(self._last_x if self._last_x is not None else current_x)
                seed_y = float(self._last_y if self._last_y is not None else current_y)
                self._kalman_filter.reset()
                self._kalman_filter.update(seed_x, seed_y)
                self._smoothed_x = seed_x
                self._smoothed_y = seed_y
                self._recovery_frames_remaining -= 1

            # 1. Kalman 2D state update with adaptive velocity-dependent noise scaling
            kx, ky = self._kalman_filter.update(float(target_x), float(target_y))

            if self._smoothed_x is None or self._smoothed_y is None:
                self._smoothed_x = float(kx)
                self._smoothed_y = float(ky)

            # 2. Configurable smoothing alpha blending
            alpha = self._config.smoothing_alpha
            self._smoothed_x = alpha * kx + (1.0 - alpha) * self._smoothed_x
            self._smoothed_y = alpha * ky + (1.0 - alpha) * self._smoothed_y

            return int(round(self._smoothed_x)), int(round(self._smoothed_y))

    def _limit_step(
        self,
        next_x: int,
        next_y: int,
        current_x: int,
        current_y: int,
    ) -> tuple[int, int]:
        """Clamp per-frame cursor travel to prevent sudden jumps."""
        ref_x = self._last_x if self._last_x is not None else current_x
        ref_y = self._last_y if self._last_y is not None else current_y
        max_step = self._config.max_step_px
        dx = next_x - ref_x
        dy = next_y - ref_y
        distance = hypot(dx, dy)
        if distance <= max_step or distance <= 0.0:
            return next_x, next_y

        scale = max_step / distance
        return (
            int(round(ref_x + dx * scale)),
            int(round(ref_y + dy * scale)),
        )

    def _clear_motion_state(self) -> None:
        """Clear state that could otherwise cause cursor jumps."""
        if self._last_x is None and self._smoothed_x is None and not getattr(self._kalman_filter, "is_initialized", False):
            return
        self._last_x = None
        self._last_y = None
        self._smoothed_x = None
        self._smoothed_y = None
        self.history_buffer.clear()
        self._is_frozen_by_ear = False
        if hasattr(self, "_kalman_filter") and self._kalman_filter is not None:
            self._kalman_filter.reset()

    def _release_drag_if_needed(self) -> None:
        """Release drag state when cursor movement is stopped."""
        if not self._drag_button_down or self._pyautogui is None:
            self._drag_button_down = False
            self._drag_mode = False
            return

        try:
            self._pyautogui.mouseUp(button="left")
        except Exception:
            logger.exception("Failed to release drag button.")
        finally:
            self._drag_button_down = False
            self._drag_mode = False

    def _load_pyautogui(self) -> Any | None:
        """Load PyAutoGUI lazily so disabled cursor control is side-effect free."""
        try:
            import pyautogui
        except Exception:
            logger.exception("PyAutoGUI could not be loaded; cursor control remains disabled.")
            return None

        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.0
        return pyautogui

    def _validate_config(self, config: CursorControllerConfig) -> None:
        """Validate cursor controller settings."""
        if config.sensitivity <= 0.0:
            raise ValueError("sensitivity must be positive.")
        if not 0.0 < config.smoothing_alpha <= 1.0:
            raise ValueError("smoothing_alpha must be in the range (0.0, 1.0].")
        if config.dead_zone_px < 0.0:
            raise ValueError("dead_zone_px cannot be negative.")
        if config.min_move_px < 0.0:
            raise ValueError("min_move_px cannot be negative.")
        if config.edge_padding_px < 0:
            raise ValueError("edge_padding_px cannot be negative.")
        if config.move_duration_seconds < 0.0:
            raise ValueError("move_duration_seconds cannot be negative.")
        if not 0.0 <= config.tracking_confidence_threshold <= 1.0:
            raise ValueError("tracking_confidence_threshold must be in [0.0, 1.0].")
        if config.max_step_px <= 0.0:
            raise ValueError("max_step_px must be positive.")
        if config.recovery_frames < 0:
            raise ValueError("recovery_frames cannot be negative.")
        if config.history_buffer_maxlen < 1:
            raise ValueError("history_buffer_maxlen must be at least 1.")
        if not 0.0 <= config.ear_freeze_threshold <= 1.0:
            raise ValueError("ear_freeze_threshold must be in [0.0, 1.0].")
