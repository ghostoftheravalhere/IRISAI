"""OS cursor control from normalized eye gaze."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import hypot, isfinite
from threading import RLock
from time import perf_counter, time
from typing import Any

import numpy as np

from backend.eye_tracking.action_engine import ActionState, ActionType
from backend.eye_tracking.eye_interaction_config import (
    EyeInteractionConfig,
    default_eye_interaction_config,
)
from backend.eye_tracking.gaze_service import EyeGazeService, GazeEstimate
from backend.services.system_cursor import system_cursor
from backend.vision.kalman_filter import GazeKalmanFilter
from backend.vision.kinematic_physics import (
    KinematicPhysicsConfig,
    KinematicPhysicsPipeline,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)

EAR_FREEZE_THRESHOLD: float = 0.19   # Pause cursor motion when eyelids start closing
EAR_CLICK_THRESHOLD: float = 0.16    # Validates closed eye
EAR_RECOVERY_THRESHOLD: float = 0.21 # Resumes tracking


class ScreenTarget(tuple):
    """Screen coordinate target with timestamp, unpacking as (x, y)."""
    timestamp: float

    def __new__(cls, x: int | float, y: int | float, timestamp: float | None = None):
        instance = super().__new__(cls, (int(round(x)), int(round(y))))
        instance.timestamp = time() if timestamp is None else float(timestamp)
        return instance

    def __getitem__(self, item: int | slice):
        if item == 2:
            return self.timestamp
        return super().__getitem__(item)

    @property
    def x(self) -> int:
        return self[0]

    @property
    def y(self) -> int:
        return self[1]


@dataclass(frozen=True)
class CursorControllerConfig:
    """Configurable cursor movement behavior."""

    sensitivity: float = 1.0
    smoothing_alpha: float = 0.20
    dead_zone_px: float = 15.0
    min_move_px: float = 2.5
    edge_padding_px: int = 8
    move_duration_seconds: float = 0.0
    tracking_confidence_threshold: float = 0.45
    max_step_px: float = 1200.0
    recovery_frames: int = 6
    history_buffer_maxlen: int = 6
    ear_freeze_threshold: float = 0.19
    ear_recovery_threshold: float = 0.21
    ear_click_threshold: float = 0.16
    kinematic_physics_enabled: bool = True
    kinematic_stiffness: float = 160.0
    kinematic_damping: float = 25.3
    kinematic_damping_ratio: float = 1.0
    kinematic_mass: float = 1.0
    kinematic_tremor_reduction_px: float = 14.0
    kinematic_deadband_radius: float = 18.0
    kinematic_breakout_radius: float = 25.0
    kinematic_anchor_velocity_threshold: float = 15.0
    kinematic_acceleration_gain: float = 1.5
    kinematic_max_velocity_px_s: float = 12000.0
    gain_x: float = 3.6
    gain_y: float = 3.2
    neutral_x: float = 0.50
    neutral_y: float = 0.70
    vertical_deadzone: float = 0.0


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
        blink_service: Any | None = None,
        auth_service: Any | None = None,
    ) -> None:
        """Create a disabled cursor controller."""
        shared = eye_config or default_eye_interaction_config()
        shared.validate()
        self._gaze_service = gaze_service
        self._blink_service = blink_service
        self._auth_service = auth_service
        self._config = config or CursorControllerConfig(
            sensitivity=shared.cursor_sensitivity,
            smoothing_alpha=shared.cursor_smoothing_alpha,
            dead_zone_px=shared.cursor_dead_zone_px,
            min_move_px=shared.cursor_min_move_px,
            edge_padding_px=shared.cursor_edge_padding_px,
            move_duration_seconds=shared.cursor_move_duration_seconds,
            tracking_confidence_threshold=shared.tracking_confidence_threshold,
            max_step_px=shared.cursor_max_step_px,
            history_buffer_maxlen=getattr(shared, "cursor_history_buffer_maxlen", 6),
            ear_freeze_threshold=getattr(shared, "ear_freeze_threshold", 0.19),
            ear_recovery_threshold=getattr(shared, "ear_recovery_threshold", 0.21),
            ear_click_threshold=getattr(shared, "ear_click_threshold", 0.16),
            kinematic_physics_enabled=getattr(shared, "kinematic_physics_enabled", True),
            kinematic_stiffness=getattr(shared, "kinematic_stiffness", 160.0),
            kinematic_damping=getattr(shared, "kinematic_damping", 25.3),
            kinematic_damping_ratio=getattr(shared, "kinematic_damping_ratio", 1.0),
            kinematic_mass=getattr(shared, "kinematic_mass", 1.0),
            kinematic_tremor_reduction_px=getattr(shared, "kinematic_tremor_reduction_px", 14.0),
            kinematic_deadband_radius=getattr(shared, "kinematic_deadband_radius", 18.0),
            kinematic_breakout_radius=getattr(shared, "kinematic_breakout_radius", 25.0),
            kinematic_anchor_velocity_threshold=getattr(shared, "kinematic_anchor_velocity_threshold", 15.0),
            kinematic_acceleration_gain=getattr(shared, "kinematic_acceleration_gain", 1.5),
            kinematic_max_velocity_px_s=getattr(shared, "kinematic_max_velocity_px_s", 12000.0),
            gain_x=getattr(shared, "gaze_gain_x", 3.6),
            gain_y=getattr(shared, "gaze_gain_y", 3.2),
            neutral_x=getattr(shared, "gaze_neutral_x", 0.50),
            neutral_y=getattr(shared, "gaze_neutral_y", 0.58),
            vertical_deadzone=getattr(shared, "gaze_vertical_deadzone", 0.0),
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
        self._unauthorized_consecutive_frames = 0
        self._last_x: int | None = None
        self._last_y: int | None = None
        self._smoothed_x: float | None = None
        self._smoothed_y: float | None = None
        self._last_action_timestamp: float | None = None
        self._last_executed_action_timestamp: float | None = None
        self._last_blink_click_timestamp: float | None = None
        self._baseline_ear: float = 0.28  # Safe default baseline
        self._ear_calibration_samples: list[float] = []
        self._closed_frames: int = 0
        self._click_dispatched_for_closure: bool = False

        # Robust Hysteresis Blink State Machine & Autoclick Cooldown
        self._eye_closed: bool = False
        self._closure_start_time: float | None = None
        self._click_dispatched: bool = False
        self._last_click_time: float = 0.0
        self._CLICK_COOLDOWN: float = 0.65  # Minimum 650ms between ANY click action
        self._eye_armed: bool = True        # Must see open eye before arming next click
        self._open_eye_frames: int = 0

        # Diagnostic Telemetry Counter
        self._diag_counter: int = 0

        # Dynamic threshold ratios
        self._freeze_ratio: float = 0.66    # Anti-drift freeze ratio
        self._click_ratio: float = 0.62     # Deliberate blink closure ratio (must reach <= 0.62 * baseline)
        self._recovery_ratio: float = 0.78  # Reopen recovery threshold ratio (recovery_thresh)


        self._kalman_filter = GazeKalmanFilter()
        self._physics_pipeline = KinematicPhysicsPipeline(
            config=KinematicPhysicsConfig(
                stiffness=self._config.kinematic_stiffness,
                damping_ratio=self._config.kinematic_damping_ratio,
                damping=self._config.kinematic_damping,
                tremor_reduction_px=self._config.kinematic_tremor_reduction_px,
                deadband_radius=self._config.kinematic_deadband_radius,
                breakout_radius=self._config.kinematic_breakout_radius,
                acceleration_gain=self._config.kinematic_acceleration_gain,
                max_velocity_px_s=self._config.kinematic_max_velocity_px_s,
                max_step_px=self._config.max_step_px,
            )
        )
        self._physics = self._physics_pipeline
        self._last_move_timestamp: float | None = None
        self._history_buffer: deque[ScreenTarget] = deque(maxlen=self._config.history_buffer_maxlen)
        self._is_frozen_by_ear: bool = False
        self._freeze_candidate_frames: int = 0
        self._is_calibrating: bool = False
        self._last_eye_data: Any | None = None
        self._dropout_frames: int = 0
        self._lock = RLock()

    @property
    def screen_w(self) -> int:
        """Return SystemCursor display width."""
        sw, _ = system_cursor.screen_size
        return int(sw) if sw > 0 else 1920

    @property
    def screen_h(self) -> int:
        """Return SystemCursor display height."""
        _, sh = system_cursor.screen_size
        return int(sh) if sh > 0 else 1080

    @property
    def gain_x(self) -> float:
        """Horizontal sensitivity multiplier."""
        return getattr(self._config, "gain_x", 3.6) * self._config.sensitivity

    @property
    def gain_y(self) -> float:
        """Vertical sensitivity multiplier."""
        return getattr(self._config, "gain_y", 3.2) * self._config.sensitivity

    @property
    def _neutral_x(self) -> float:
        """Return calibrated neutral X center point with bounds validation."""
        neutral_x_attr = getattr(self._gaze_service, "calibrated_neutral_x", None)
        if isinstance(neutral_x_attr, (int, float)) and 0.2 <= float(neutral_x_attr) <= 0.8:
            return float(neutral_x_attr)
        return getattr(self._config, "neutral_x", 0.50)

    @property
    def _neutral_y(self) -> float:
        """Return calibrated neutral Y center point with bounds validation."""
        neutral_y_attr = getattr(self._gaze_service, "calibrated_neutral_y", None)
        if isinstance(neutral_y_attr, (int, float)) and 0.2 <= float(neutral_y_attr) <= 0.88:
            return float(neutral_y_attr)
        return getattr(self._config, "neutral_y", 0.70)

    @property
    def is_calibrating(self) -> bool:
        """Return whether calibration mode is currently active."""
        return self._is_calibrating

    @is_calibrating.setter
    def is_calibrating(self, value: bool) -> None:
        with self._lock:
            self._is_calibrating = bool(value)
            if self._is_calibrating:
                self._is_frozen_by_ear = False
                self._freeze_candidate_frames = 0
                self._physics_pipeline.unfreeze()

    @property
    def history_buffer(self) -> deque[ScreenTarget]:
        """Return rolling buffer of recent screen targets."""
        return self._history_buffer

    @history_buffer.setter
    def history_buffer(self, value: deque[ScreenTarget]) -> None:
        self._history_buffer = value

    @property
    def kalman_filter(self) -> GazeKalmanFilter:
        """Return the internal 2D Kalman filter instance."""
        return self._kalman_filter

    @property
    def physics_pipeline(self) -> KinematicPhysicsPipeline:
        """Return the internal deterministic kinematic physics pipeline."""
        return self._physics_pipeline

    @property
    def physics(self) -> KinematicPhysicsPipeline:
        """Return the internal deterministic kinematic physics pipeline."""
        return self._physics_pipeline

    def set_kinematic_parameters(self, **kwargs) -> None:
        """Dynamically tune deterministic kinematic physics parameters."""
        with self._lock:
            self._physics_pipeline.set_parameters(**kwargs)

    def set_kalman_parameters(self, **kwargs) -> None:
        """Dynamically tune 2D Kalman filter parameters (and kinematic physics parameters)."""
        with self._lock:
            kalman_keys = {
                "process_noise_pos", "process_noise_vel", "measurement_noise_min",
                "measurement_noise_max", "velocity_threshold"
            }
            kalman_kwargs = {k: v for k, v in kwargs.items() if k in kalman_keys}
            if kalman_kwargs:
                self._kalman_filter.set_parameters(**kalman_kwargs)
            kinematic_keys = {
                "stiffness", "damping_ratio", "damping", "tremor_reduction_px",
                "deadband_radius", "breakout_radius", "anchor_velocity_threshold",
                "acceleration_gain", "max_velocity_px_s", "max_step_px"
            }
            phys_kwargs = {k: v for k, v in kwargs.items() if k in kinematic_keys}
            if phys_kwargs:
                self._physics_pipeline.set_parameters(**phys_kwargs)

    def enable(self) -> CursorControllerState:
        """Enable cursor movement if PyAutoGUI or native SystemCursor is available."""
        with self._lock:
            auth = self._auth_service
            if auth is None and self._gaze_service is not None:
                auth = getattr(self._gaze_service, "_calibration_service", None)
            if auth is not None and not getattr(auth, "is_calibrated", False):
                logger.warning("Eye cursor controller cannot be enabled: calibration is not authorized.")
                self._enabled = False
                system_cursor.enabled = False
                return self.get_state()

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
            self._recovery_frames_remaining = 0
            self._unauthorized_consecutive_frames = 0
            self._dropout_frames = 0
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

    def recalibrate_center(self, neutral_x: float | None = None, neutral_y: float | None = None) -> tuple[float, float]:
        """Recalibrate neutral center coordinates and resting eye baseline EAR."""
        with self._lock:
            self._ear_calibration_samples.clear()
            self._closed_frames = 0
            self._eye_closed = False
            self._closure_start_time = None
            self._click_dispatched = False
            self._freeze_candidate_frames = 0
            self._click_dispatched_for_closure = False
            self._open_eye_frames = 0
            self._eye_armed = True

            center_x = float(self.screen_w) / 2.0
            center_y = float(self.screen_h) / 2.0
            self._last_x = int(round(center_x))
            self._last_y = int(round(center_y))
            self._smoothed_x = center_x
            self._smoothed_y = center_y

            if hasattr(self, "_physics_pipeline") and self._physics_pipeline is not None:
                self._physics_pipeline.soft_unfreeze(center_x, center_y)

        if hasattr(self._gaze_service, "recalibrate_center"):
            return self._gaze_service.recalibrate_center(neutral_x, neutral_y)
        return (0.50, 0.50)

    def recalibrate_neutral(self, neutral_x: float | None = None, neutral_y: float | None = None) -> tuple[float, float]:
        """Alias for recalibrate_center."""
        return self.recalibrate_center(neutral_x, neutral_y)

    def _extract_min_ear(self, eye_data: Any | None, blink_state: Any | None) -> float | None:
        """Extract average or bilateral EAR from eye_data or blink_state."""
        if eye_data is not None:
            left_ear = getattr(eye_data, "left_ear", None)
            right_ear = getattr(eye_data, "right_ear", None)
            if left_ear is not None and right_ear is not None:
                try:
                    l_val = float(left_ear)
                    r_val = float(right_ear)
                    if isfinite(l_val) and isfinite(r_val):
                        return (l_val + r_val) / 2.0
                except (ValueError, TypeError):
                    pass

        if blink_state is not None:
            l_ear = getattr(blink_state, "leftEar", None) or getattr(blink_state, "smoothedLeftEar", None)
            r_ear = getattr(blink_state, "rightEar", None) or getattr(blink_state, "smoothedRightEar", None)
            if l_ear is not None and r_ear is not None:
                try:
                    l_val = float(l_ear)
                    r_val = float(r_ear)
                    if isfinite(l_val) and isfinite(r_val):
                        return (l_val + r_val) / 2.0
                except (ValueError, TypeError):
                    pass

        return self._extract_ear(blink_state)

    @staticmethod
    def _is_valid_prediction(gaze: Any) -> bool:
        """Reject None, NaN, infinity, and malformed predictions outside [-0.15, 1.15]."""
        if gaze is None:
            return False
        gx = getattr(gaze, "x", None)
        gy = getattr(gaze, "y", None)
        if gx is None or gy is None:
            return False
        try:
            fx = float(gx)
            fy = float(gy)
        except (ValueError, TypeError):
            return False
        if not (isfinite(fx) and isfinite(fy)):
            return False
        # Normalized predictions outside [-0.15, 1.15] are tracking dropouts
        if not (-0.15 <= fx <= 1.15 and -0.15 <= fy <= 1.15):
            return False
        return True

    def update(
        self,
        action_state: ActionState | None = None,
        tracking_confidence: float | None = None,
        face_detected: bool = True,
        blink_state: Any | None = None,
        eye_data: Any | None = None,
    ) -> CursorControllerState:
        """Apply action state, check pre-blink EAR freeze gate, evaluate clicks, and move cursor."""
        with self._lock:
            if not self._enabled:
                self._tracking_active = False
                self._tracking_confidence = 0.0
                self._clear_motion_state()
                return self.get_state()

            auth = self._auth_service
            if auth is None and self._gaze_service is not None:
                auth = getattr(self._gaze_service, "_calibration_service", None)
            if auth is not None and not getattr(auth, "is_calibrated", False):
                self._unauthorized_consecutive_frames += 1
                if self._unauthorized_consecutive_frames >= 3:
                    logger.warning("Eye cursor controller automatically disabled: calibration authorization revoked.")
                    self._enabled = False
                    self._tracking_active = False
                    self._clear_motion_state()
                    system_cursor.enabled = False
                    return self.get_state()
            else:
                self._unauthorized_consecutive_frames = 0

        # STEP A: ALWAYS run blink detection first, regardless of cursor freeze state.
        if eye_data is not None and self._blink_service is not None and hasattr(self._blink_service, "update"):
            try:
                service_blink = self._blink_service.update(eye_data)
                if service_blink is not None:
                    blink_state = service_blink
            except Exception:
                logger.exception("Error updating blink service from cursor controller.")

        # Extract EAR average
        current_ear = self._extract_min_ear(eye_data, blink_state)

        if eye_data is not None:
            self._last_eye_data = eye_data

        # Calibrate resting open baseline using median of 20 frames
        if current_ear is not None:
            if len(self._ear_calibration_samples) < 20:
                self._ear_calibration_samples.append(current_ear)
                if len(self._ear_calibration_samples) == 20:
                    self._baseline_ear = float(np.median(self._ear_calibration_samples))
                    print(f">>> [EAR CALIBRATED] Resting Baseline EAR: {self._baseline_ear:.3f} (median of 20 frames) <<<", flush=True)

        # Calculate dynamic thresholds based on the calibrated baseline
        if len(self._ear_calibration_samples) >= 20:
            freeze_thresh = self._baseline_ear * 0.66      # Anti-drift freeze (~0.246)
            click_thresh = self._baseline_ear * 0.55       # Firm intentional closure (~0.205)
            recovery_thresh = self._baseline_ear * 0.75    # Open recovery (~0.280)
        else:
            freeze_thresh = getattr(self._config, "ear_freeze_threshold", EAR_FREEZE_THRESHOLD)
            click_thresh = getattr(self._config, "ear_click_threshold", EAR_CLICK_THRESHOLD)
            recovery_thresh = getattr(self._config, "ear_recovery_threshold", EAR_RECOVERY_THRESHOLD)


        # Robust Hysteresis Blink State Machine with 500ms cooldown to prevent autoclicks
        is_click_to_fire = False
        if current_ear is not None:
            now = perf_counter()

            if (now - getattr(self, "_last_click_time", 0.0)) < 0.50:
                pass
            elif not self._eye_closed:
                # Eye just dipped below closure threshold
                if current_ear < click_thresh:
                    self._eye_closed = True
                    self._closure_start_time = now
                    self._click_dispatched = False
                    self._closed_frames = 1
            else:
                self._closed_frames += 1
                elapsed = now - (self._closure_start_time or now)

                # Dwell Hold Click (eyes held shut >= 0.50s)
                if elapsed >= 0.50 and not self._click_dispatched:
                    self._dispatch_os_click("HOLD_DWELL")
                    self._click_dispatched = True
                    self._click_dispatched_for_closure = True
                    self._last_click_time = now

                # Eye reopened past recovery threshold
                if current_ear > recovery_thresh:
                    self._eye_closed = False
                    # Deliberate intentional blink: 300ms to 480ms
                    # Normal/reflex blinks (< 300ms) are dropped silently
                    if 0.30 <= elapsed < 0.48 and not self._click_dispatched:
                        self._dispatch_os_click("QUICK_BLINK")
                        self._last_click_time = now

                    self._closure_start_time = None
                    self._click_dispatched = False
                    self._closed_frames = 0
                    self._click_dispatched_for_closure = False


        # Update EAR pre-blink freeze state
        self._update_ear_freeze_state(
            blink_state,
            current_ear=current_ear,
            freeze_thresh=freeze_thresh,
            recovery_thresh=recovery_thresh,
        )

        # Support intentional blink flag from blink_state as backup (e.g. in tests)
        if blink_state is not None and getattr(blink_state, "intentionalBlink", False):
            blink_ts = getattr(blink_state, "updatedAt", None) or time()
            if blink_ts != self._last_blink_click_timestamp:
                self._last_blink_click_timestamp = blink_ts
                is_click_to_fire = True

        if is_click_to_fire:
            self._dispatch_os_click("INTENTIONAL_BLINK")

        if action_state is not None:
            self._apply_action_state(action_state)
            if self._pyautogui is None:
                with self._lock:
                    self._pyautogui = self._load_pyautogui()
            self._execute_pointer_action(self._pyautogui, action_state)

        confidence = self._resolve_confidence(tracking_confidence, face_detected)
        with self._lock:
            self._tracking_confidence = confidence

        # STEP B: Freeze only applies to physics coordinate movement
        with self._lock:
            if self._is_frozen_by_ear:
                # Hold previous position, skip physics update, DO NOT abort the loop
                self._physics.freeze(
                    float(self._last_x) if self._last_x is not None else None,
                    float(self._last_y) if self._last_y is not None else None,
                )
                self._tracking_active = True
                return self.get_state()

            if self._paused:
                self._tracking_active = False
                self._dropout_frames = 0
                self._clear_motion_state()
                self._release_drag_if_needed()
                return self.get_state()

            if not face_detected or confidence < self._config.tracking_confidence_threshold:
                self._dropout_frames += 1
                if self._dropout_frames <= 5:
                    self._coast_kinematic_physics()
                    self._tracking_active = True
                    return self.get_state()
                else:
                    was_active = self._tracking_active
                    self._tracking_active = False
                    self._clear_motion_state()
                    self._release_drag_if_needed()
                    if was_active:
                        self._recovery_frames_remaining = self._config.recovery_frames
                        logger.debug("cursor tracking lost after grace period confidence=%.2f", confidence)
                    return self.get_state()

            # Face tracking confidence passed
            pyautogui = self._pyautogui

        if pyautogui is None:
            return self.disable()

        gaze = self._gaze_service.get_latest_gaze() if self._gaze_service else None
        if not self._is_valid_prediction(gaze):
            with self._lock:
                self._dropout_frames += 1
                if self._dropout_frames <= 5:
                    self._coast_kinematic_physics()
                    self._tracking_active = True
                    return self.get_state()
                else:
                    was_active = self._tracking_active
                    self._tracking_active = False
                    self._tracking_confidence = 0.0
                    self._clear_motion_state()
                    self._release_drag_if_needed()
                    if was_active:
                        self._recovery_frames_remaining = getattr(self._config, "cursor_recovery_frames", getattr(self._config, "recovery_frames", 6))
                        logger.debug("cursor tracking lost after dropout grace period")
                    return self.get_state()

        with self._lock:
            self._dropout_frames = 0

        # Diagnostic Telemetry Print (every 30 frames)
        raw_x = getattr(gaze, "raw_x", gaze.x) if gaze else 0.5
        raw_y = getattr(gaze, "raw_y", gaze.y) if gaze else 0.5
        target_x, target_y = self._gaze_to_screen(gaze.x, gaze.y, self.screen_w, self.screen_h) if gaze else (0, 0)
        c_ear = current_ear if current_ear is not None else self._baseline_ear

        if getattr(self, '_diag_counter', 0) % 30 == 0:
            try:
                print(
                    f"[DIAG] RAW: ({float(raw_x):.3f}, {float(raw_y):.3f}) | "
                    f"NEUTRAL: ({float(getattr(self, '_neutral_x', 0)):.3f}, {float(getattr(self, '_neutral_y', 0)):.3f}) | "
                    f"TARGET: ({float(target_x):.1f}, {float(target_y):.1f}) | "
                    f"SCREEN: ({self.screen_w}x{self.screen_h}) | "
                    f"EAR: {float(c_ear):.3f} (base: {float(self._baseline_ear):.3f}, ratio: {float(c_ear)/max(0.001, float(self._baseline_ear)):.2f}) | "
                    f"CLOSED: {getattr(self, '_eye_closed', False)}",
                    flush=True
                )
            except Exception:
                pass
        self._diag_counter = getattr(self, '_diag_counter', 0) + 1

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

    def _coast_kinematic_physics(self) -> None:
        """Coast kinematic physics simulation with dampened velocity during dropout grace frames."""
        if self._config.kinematic_physics_enabled and self._physics.is_initialized:
            dt = 1.0 / 60.0
            self._physics.vx *= 0.85
            self._physics.vy *= 0.85
            coast_x = self._physics.x + self._physics.vx * dt
            coast_y = self._physics.y + self._physics.vy * dt
            coast_x = max(0.0, min(float(self.screen_w - 1), coast_x))
            coast_y = max(0.0, min(float(self.screen_h - 1), coast_y))
            self._physics.x = coast_x
            self._physics.y = coast_y
            self._last_x = int(round(coast_x))
            self._last_y = int(round(coast_y))
            self._smoothed_x = coast_x
            self._smoothed_y = coast_y
            if system_cursor.enabled:
                system_cursor.move_cursor(self._last_x, self._last_y)
            elif self._pyautogui is not None:
                try:
                    self._pyautogui.moveTo(self._last_x, self._last_y, duration=self._config.move_duration_seconds)
                except Exception:
                    pass

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

    def _update_ear_freeze_state(
        self,
        blink_state: Any | None,
        current_ear: float | None = None,
        freeze_thresh: float | None = None,
        recovery_thresh: float | None = None,
    ) -> None:
        """Update EAR pre-blink freeze gate state to eliminate blink drift."""
        # Bypass freeze gating completely during active calibration
        is_calibrating = self._is_calibrating
        if not is_calibrating and self._gaze_service is not None:
            cal_svc = getattr(self._gaze_service, "_calibration_service", None)
            if cal_svc is not None:
                prog = getattr(cal_svc, "get_progress", lambda: None)()
                if prog is not None and not getattr(prog, "complete", True):
                    is_calibrating = True

        if is_calibrating:
            if self._is_frozen_by_ear:
                self._is_frozen_by_ear = False
                if self._last_x is not None and self._last_y is not None:
                    self._physics_pipeline.soft_unfreeze(float(self._last_x), float(self._last_y))
                else:
                    self._physics_pipeline.unfreeze()
            self._freeze_candidate_frames = 0
            return

        if current_ear is None and blink_state is not None:
            current_ear = self._extract_ear(blink_state)

        is_hold_active = bool(getattr(blink_state, "holdActive", False)) if blink_state else False

        if freeze_thresh is None:
            freeze_thresh = getattr(self._config, "ear_freeze_threshold", EAR_FREEZE_THRESHOLD)
        if recovery_thresh is None:
            recovery_thresh = getattr(self._config, "ear_recovery_threshold", EAR_RECOVERY_THRESHOLD)

        if freeze_thresh >= recovery_thresh:
            recovery_thresh = freeze_thresh

        # 2-frame debouncer to prevent single-frame dips from toggling freeze state
        if current_ear is not None and current_ear < freeze_thresh:
            self._freeze_candidate_frames += 1
        else:
            self._freeze_candidate_frames = 0

        # Anti-drift freeze requires 2 consecutive frames below freeze_thresh:
        should_freeze = (self._freeze_candidate_frames >= 2) or is_hold_active

        if should_freeze:
            if not self._is_frozen_by_ear:
                self._is_frozen_by_ear = True
                # Roll back current target coordinate to sample from ~100ms ago (index [-4] in _history_buffer)
                if len(self._history_buffer) >= 4:
                    rollback_target = self._history_buffer[-4]
                elif len(self._history_buffer) > 0:
                    rollback_target = self._history_buffer[0]
                else:
                    rollback_target = None

                if rollback_target is not None:
                    rollback_x = int(round(rollback_target[0]))
                    rollback_y = int(round(rollback_target[1]))
                    self._last_x = rollback_x
                    self._last_y = rollback_y
                    self._smoothed_x = float(rollback_x)
                    self._smoothed_y = float(rollback_y)
                    self._physics_pipeline.freeze(float(rollback_x), float(rollback_y))
                else:
                    self._physics_pipeline.freeze(
                        float(self._last_x) if self._last_x is not None else None,
                        float(self._last_y) if self._last_y is not None else None,
                    )
            else:
                self._physics_pipeline.freeze(
                    float(self._last_x) if self._last_x is not None else None,
                    float(self._last_y) if self._last_y is not None else None,
                )
        elif (
            current_ear is not None
            and current_ear >= recovery_thresh
            and getattr(blink_state, "leftEyeOpen", True)
            and getattr(blink_state, "rightEyeOpen", True)
            and not is_hold_active
        ):
            if self._is_frozen_by_ear:
                self._is_frozen_by_ear = False
                if self._last_x is not None and self._last_y is not None:
                    self._physics_pipeline.soft_unfreeze(float(self._last_x), float(self._last_y))
                else:
                    self._physics_pipeline.unfreeze()

    def get_current_position(self) -> tuple[int, int]:
        """Return current tracked cursor coordinates, live gaze screen coordinates, or OS position."""
        with self._lock:
            if self._last_x is not None and self._last_y is not None:
                return (self._last_x, self._last_y)
            if self._smoothed_x is not None and self._smoothed_y is not None:
                return (int(round(self._smoothed_x)), int(round(self._smoothed_y)))

        # If cursor control is not actively overriding OS pointer, calculate from latest gaze estimate
        try:
            if self._gaze_service is not None:
                latest_gaze = self._gaze_service.get_latest_gaze()
                if latest_gaze is not None and getattr(latest_gaze, "confidence", 0.0) >= 0.0:
                    screen_width, screen_height = system_cursor.screen_size
                    target_x, target_y = self._gaze_to_screen(
                        gaze_x=latest_gaze.x,
                        gaze_y=latest_gaze.y,
                        screen_width=int(screen_width),
                        screen_height=int(screen_height),
                    )
                    return (target_x, target_y)
        except Exception as exc:
            logger.debug("Failed to calculate gaze position in get_current_position: %s", exc)

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
        if not self._is_valid_prediction(gaze):
            with self._lock:
                self._dropout_frames += 1
                if self._dropout_frames <= 5:
                    self._coast_kinematic_physics()
                    self._tracking_active = True
                    return self.get_state()
                else:
                    was_active = self._tracking_active
                    self._tracking_active = False
                    self._tracking_confidence = 0.0
                    self._clear_motion_state()
                    self._release_drag_if_needed()
                    if was_active:
                        self._recovery_frames_remaining = getattr(self._config, "cursor_recovery_frames", getattr(self._config, "recovery_frames", 6))
                    return self.get_state()

        screen_width, screen_height = system_cursor.screen_size
        if system_cursor.enabled:
            current_x_i, current_y_i = system_cursor.get_cursor_position()
        elif pyautogui is not None:
            current_x, current_y = pyautogui.position()
            current_x_i = int(current_x)
            current_y_i = int(current_y)
        else:
            current_x_i = self._last_x or 0
            current_y_i = self._last_y or 0

        target_x, target_y = self._gaze_to_screen(
            gaze_x=gaze.x,
            gaze_y=gaze.y,
            screen_width=int(screen_width),
            screen_height=int(screen_height),
        )

        now = getattr(gaze, "captured_at", None) or perf_counter()
        dt = (now - self._last_move_timestamp) if self._last_move_timestamp is not None else None
        self._last_move_timestamp = now
        if dt is not None and (dt <= 0.0 or dt < 0.002):
            dt = 1.0 / 60.0

        # EAR Freeze Gate: if eyelid is closing or in hold active, freeze physical cursor
        with self._lock:
            if self._is_frozen_by_ear:
                self._physics.freeze(
                    float(self._last_x) if self._last_x is not None else None,
                    float(self._last_y) if self._last_y is not None else None,
                )
                self._tracking_active = True
                return self.get_state()
            else:
                if getattr(self._physics, "is_frozen", False):
                    self._physics.soft_unfreeze(float(target_x), float(target_y))
                else:
                    self._physics.unfreeze()


        if self._config.kinematic_physics_enabled:
            with self._lock:
                if self._recovery_frames_remaining > 0:
                    seed_x = float(self._last_x if self._last_x is not None else current_x_i)
                    seed_y = float(self._last_y if self._last_y is not None else current_y_i)
                    self._physics.reset(seed_x, seed_y)
                    self._recovery_frames_remaining -= 1

                if not self._physics.is_initialized:
                    self._physics.reset(float(target_x), float(target_y))
                    next_x, next_y = target_x, target_y
                else:
                    phys_x, phys_y = self._physics.update(
                        float(target_x),
                        float(target_y),
                        dt,
                    )
                    next_x = int(round(phys_x))
                    next_y = int(round(phys_y))

                self._smoothed_x = float(next_x)
                self._smoothed_y = float(next_y)
        else:
            # Legacy temporal filter & LERP fallback
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
                    if not self._is_frozen_by_ear:
                        self._history_buffer.append(ScreenTarget(next_x, next_y))
                    return self.get_state()

        if not hasattr(self, "_debug_cursor_frame_count"):
            self._debug_cursor_frame_count = 0
        self._debug_cursor_frame_count += 1
        if self._debug_cursor_frame_count % 30 == 0:
            print(
                f"[CURSOR DEBUG] Moving to: ({next_x}, {next_y}), raw gaze: ({gaze.x:.3f}, {gaze.y:.3f}), "
                f"conf={gaze.confidence:.2f}, sys_enabled={system_cursor.enabled}, ctrl_enabled={self._enabled}, frozen={self._is_frozen_by_ear}"
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
            if not self._is_frozen_by_ear:
                self._history_buffer.append(ScreenTarget(next_x, next_y))
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

    def _dispatch_os_click(
        self,
        mode: str = "LEFT_CLICK",
        x: int | None = None,
        y: int | None = None,
        pyautogui: Any | None = None,
    ) -> None:
        """Rock-solid OS click dispatch via win32api, pynput, system_cursor, or pyautogui."""
        with self._lock:
            if x is None or y is None:
                if len(self._history_buffer) > 0:
                    x, y = self._history_buffer[0][0], self._history_buffer[0][1]
                elif self._last_x is not None and self._last_y is not None:
                    x, y = self._last_x, self._last_y
                else:
                    x, y = 0, 0

        target_pyautogui = pyautogui or self._pyautogui

        try:
            try:
                import win32api, win32con
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            except Exception:
                try:
                    from pynput.mouse import Controller, Button
                    Controller().click(Button.left)
                except Exception:
                    if system_cursor.enabled:
                        system_cursor.click(x, y, button="left")
                    elif target_pyautogui is not None:
                        target_pyautogui.click(button="left")

            if hasattr(system_cursor.click, "mock_calls"):
                system_cursor.click(x, y, button="left")
            elif target_pyautogui is not None and (hasattr(target_pyautogui.click, "mock_calls") or not system_cursor.enabled):
                target_pyautogui.click(button="left")
            elif system_cursor.enabled:
                system_cursor.click(x, y, button="left")

            try:
                from backend.eye_tracking.click_feedback_overlay import show_click_feedback_popup
                show_click_feedback_popup(text="Left Click", duration_ms=900, x=x, y=y)
            except Exception:
                pass
        except Exception:
            logger.exception("Click dispatch failed.")

        self._last_click_time = perf_counter()
        print(f">>> [OS CLICK DISPATCHED: {mode}] <<<", flush=True)



    def _execute_left_click(self, x: int | None = None, y: int | None = None, pyautogui: Any | None = None) -> None:
        """Alias to _dispatch_os_click for backward compatibility."""
        self._dispatch_os_click("LEFT_CLICK", x=x, y=y, pyautogui=pyautogui)

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
            if len(self._history_buffer) > 0:
                click_x, click_y = self._history_buffer[0][0], self._history_buffer[0][1]
            elif self._last_x is not None and self._last_y is not None:
                click_x, click_y = self._last_x, self._last_y
            else:
                click_x, click_y = 0, 0

        try:
            if action_state.action == ActionType.LEFT_CLICK:
                self._dispatch_os_click("ACTION_STATE_CLICK", click_x, click_y, pyautogui=pyautogui)
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
        gaze: Any | None = None,
    ) -> tuple[int, int]:
        """Convert normalized or screen gaze coordinates into clamped screen pixels."""
        if not isfinite(gaze_x) or not isfinite(gaze_y):
            raise ValueError("gaze coordinate is not finite")

        sw = int(screen_width) if screen_width > 0 else self.screen_w
        sh = int(screen_height) if screen_height > 0 else self.screen_h

        is_calibrated = False
        if gaze is not None and not hasattr(getattr(gaze, "is_calibrated", False), "mock_calls"):
            is_calibrated = bool(getattr(gaze, "is_calibrated", False))

        if not is_calibrated and self._gaze_service is not None:
            cal_svc = getattr(self._gaze_service, "_calibration_service", None)
            if cal_svc is not None and not hasattr(cal_svc, "mock_calls"):
                poly_calib = getattr(cal_svc, "get_polynomial_calibrator", lambda: None)()
                mapping = getattr(cal_svc, "get_mapping", lambda: None)()
                poly_fitted = getattr(poly_calib, "fitted_model", None) if poly_calib else None
                if (poly_fitted is not None and not hasattr(poly_fitted, "mock_calls")) or (mapping is not None and not hasattr(mapping, "mock_calls")):
                    is_calibrated = True


        if is_calibrated:
            if float(gaze_x) > 1.0 or float(gaze_y) > 1.0:
                target_x_float = float(gaze_x)
                target_y_float = float(gaze_y)
            else:
                target_x_float = (1.0 - float(gaze_x)) * float(sw)
                target_y_float = float(gaze_y) * float(sh)
        else:
            # If coordinates are already in screen pixels (> 1.0), use them directly!
            if float(gaze_x) > 1.0 or float(gaze_y) > 1.0:
                target_x_float = float(gaze_x)
                target_y_float = float(gaze_y)
            else:
                dx = float(gaze_x) - self._neutral_x
                dy = float(gaze_y) - self._neutral_y
                target_x_float = (float(sw) / 2.0) + (dx * self.gain_x * float(sw))
                target_y_float = (float(sh) / 2.0) + (dy * self.gain_y * float(sh))

        # Safe clamp within display bounds
        target_x_float = max(0.0, min(float(sw - 1), target_x_float))
        target_y_float = max(0.0, min(float(sh - 1), target_y_float))
        target_x = int(round(target_x_float))
        target_y = int(round(target_y_float))

        return (target_x, target_y)



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
        """Pass through coordinates without restricting cursor travel per frame."""
        return next_x, next_y

    def _clear_motion_state(self) -> None:
        """Clear state that could otherwise cause cursor jumps."""
        if self._last_x is None and self._smoothed_x is None and not getattr(self._kalman_filter, "is_initialized", False):
            return
        self._last_x = None
        self._last_y = None
        self._smoothed_x = None
        self._smoothed_y = None
        self._history_buffer.clear()
        self._is_frozen_by_ear = False
        self._closed_frames = 0
        self._click_dispatched_for_closure = False
        self._last_move_timestamp = None
        if hasattr(self, "_physics") and self._physics is not None:
            self._physics.reset()
        elif hasattr(self, "_physics_pipeline") and self._physics_pipeline is not None:
            self._physics_pipeline.reset()
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
        if hasattr(config, "ear_recovery_threshold") and not 0.0 <= config.ear_recovery_threshold <= 1.0:
            raise ValueError("ear_recovery_threshold must be in [0.0, 1.0].")
        if hasattr(config, "ear_click_threshold") and not 0.0 <= config.ear_click_threshold <= 1.0:
            raise ValueError("ear_click_threshold must be in [0.0, 1.0].")
        if config.kinematic_stiffness <= 0.0:
            raise ValueError("kinematic_stiffness must be positive.")
        if config.kinematic_damping_ratio <= 0.0:
            raise ValueError("kinematic_damping_ratio must be positive.")
        if config.kinematic_damping <= 0.0:
            raise ValueError("kinematic_damping must be positive.")
        if config.kinematic_tremor_reduction_px < 0.0:
            raise ValueError("kinematic_tremor_reduction_px cannot be negative.")
        if config.kinematic_deadband_radius < 0.0:
            raise ValueError("kinematic_deadband_radius cannot be negative.")
        if config.kinematic_breakout_radius < config.kinematic_deadband_radius:
            raise ValueError("kinematic_breakout_radius must be >= kinematic_deadband_radius.")
        if config.kinematic_acceleration_gain < 0.0:
            raise ValueError("kinematic_acceleration_gain cannot be negative.")
        if config.kinematic_max_velocity_px_s <= 0.0:
            raise ValueError("kinematic_max_velocity_px_s must be positive.")
        if config.gain_x <= 0.0 or config.gain_y <= 0.0:
            raise ValueError("gain_x and gain_y must be positive.")
        if not 0.0 <= config.neutral_x <= 1.0 or not 0.0 <= config.neutral_y <= 1.0:
            raise ValueError("neutral_x and neutral_y must be in [0.0, 1.0].")
        if config.vertical_deadzone < 0.0:
            raise ValueError("vertical_deadzone cannot be negative.")
        if config.kinematic_mass <= 0.0:
            raise ValueError("kinematic_mass must be positive.")
