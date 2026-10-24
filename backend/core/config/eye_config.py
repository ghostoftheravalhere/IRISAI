"""Central configuration for the eye interaction pipeline.

All EAR, blink, gesture, cursor, and calibration thresholds live here so
accessibility behavior can be tuned without hunting through services.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.core.config.settings import settings

# Sprint 1: shared MediaPipe EAR indices remove duplicated constants.
RIGHT_EAR_LANDMARK_INDICES = (33, 160, 158, 133, 153, 144)
LEFT_EAR_LANDMARK_INDICES = (362, 385, 387, 263, 373, 380)


@dataclass(frozen=True)
class EyeInteractionConfig:
    """Production thresholds for intentional eye interaction.

    Natural blinks are ignored. Only held (intentional) blinks in the
    configured duration window produce gestures.
    """

    # --- EAR classification ---
    ear_close_threshold: float = 0.18
    ear_open_threshold: float = 0.21
    ear_freeze_threshold: float = 0.19
    ear_recovery_threshold: float = 0.21
    ear_click_threshold: float = 0.16
    ear_smoothing_alpha: float = 0.35

    # --- Intentional blink timing (milliseconds) ---
    # Natural blinks are typically 100–350 ms and must never click.
    intentional_blink_min_ms: float = 400.0
    intentional_blink_max_ms: float = 1200.0
    both_eye_coalesce_ms: float = 220.0

    # Frame confirmation floors (scaled with measured FPS, then clamped).
    closed_frames_min: int = 3
    open_frames_min: int = 2
    fps_min_for_thresholds: float = 12.0
    fps_max_for_thresholds: float = 60.0
    closed_frames_max: int = 8
    open_frames_max: int = 5
    fps_closed_seconds: float = 0.10
    fps_open_seconds: float = 0.066
    fps_ema_alpha: float = 0.2
    blink_debug_log_interval_s: float = 0.5

    # --- Gesture interpretation ---
    # Keep the double window short so single clicks are not delayed ~750 ms.
    double_long_blink_window_ms: float = 400.0
    gesture_cooldown_ms: float = 500.0
    gesture_display_ms: float = 450.0

    # --- Action engine ---
    action_cooldown_ms: float = 500.0

    # --- Gaze / cursor ---
    # Kinematic Physics Pipeline (v2.4.6)
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
    gaze_gain_x: float = 3.6
    gaze_gain_y: float = 3.2
    gaze_neutral_x: float = 0.50
    gaze_neutral_y: float = 0.70
    gaze_vertical_deadzone: float = 0.0

    # Lower EMA alphas = heavier smoothing (less noisy, modest added lag).
    gaze_smoothing_alpha: float = 0.28
    cursor_sensitivity: float = 0.92
    cursor_smoothing_alpha: float = 0.20
    cursor_dead_zone_px: float = 15.0
    cursor_min_move_px: float = 2.5
    cursor_edge_padding_px: int = 8
    cursor_move_duration_seconds: float = 0.0
    cursor_max_step_px: float = 1200.0
    cursor_recovery_frames: int = 6
    cursor_history_buffer_maxlen: int = 6
    tracking_confidence_threshold: float = 0.45

    # --- Calibration sampling ---
    # Wait for gaze to settle, then average many frames so one noisy frame
    # cannot dominate the polynomial fit.
    calibration_stabilize_ms: float = 400.0
    calibration_sample_count: int = 30
    calibration_sample_timeout_ms: float = 4000.0
    calibration_sample_poll_ms: float = 20.0
    calibration_min_valid_samples: int = 15
    calibration_blink_ear_threshold: float = 0.18
    # Reject frames whose eye-center MAD exceeds this robust z-score.
    calibration_outlier_mad_scale: float = 2.5
    # Reject consecutive samples with sudden head / landmark jumps.
    calibration_max_center_jump: float = 0.035
    # Reject a capture whose inlier gaze cloud is still too spread out
    # (user still settling / head moving). Units: normalized face space.
    calibration_max_sample_dispersion: float = 0.012

    # --- Calibration quality & Validation Gates ---
    # Score = 1 / (1 + rmse * 5).
    calibration_quality_threshold: float = 0.45
    calibration_rmse_scale: float = 5.0
    calibration_good_score_threshold: float = 0.58
    validation_mean_norm_threshold: float = 0.08
    validation_max_norm_threshold: float = 0.15
    calibration_max_condition_number: float = 10000.0
    calibration_mode: str = "16-point"

    # --- Overlay ---
    # "normal" for demo polish, "debug" for developer diagnostics.
    overlay_mode: str = "normal"

    def validate(self) -> None:
        """Raise ``ValueError`` when any threshold is inconsistent."""
        if not 0.0 < self.ear_close_threshold < 1.0:
            raise ValueError("ear_close_threshold must be in (0.0, 1.0).")
        if not 0.0 < self.ear_open_threshold < 1.0:
            raise ValueError("ear_open_threshold must be in (0.0, 1.0).")
        if self.ear_open_threshold <= self.ear_close_threshold:
            raise ValueError("ear_open_threshold must be > ear_close_threshold.")
        if not 0.0 < self.ear_smoothing_alpha <= 1.0:
            raise ValueError("ear_smoothing_alpha must be in (0.0, 1.0].")
        if self.intentional_blink_min_ms <= 0.0:
            raise ValueError("intentional_blink_min_ms must be positive.")
        if self.intentional_blink_max_ms < self.intentional_blink_min_ms:
            raise ValueError("intentional_blink_max_ms must be >= intentional_blink_min_ms.")
        if self.both_eye_coalesce_ms < 0.0:
            raise ValueError("both_eye_coalesce_ms cannot be negative.")
        if self.closed_frames_min < 1 or self.open_frames_min < 1:
            raise ValueError("frame confirmation thresholds must be at least 1.")
        if self.closed_frames_max < self.closed_frames_min:
            raise ValueError("closed_frames_max must be >= closed_frames_min.")
        if self.open_frames_max < self.open_frames_min:
            raise ValueError("open_frames_max must be >= open_frames_min.")
        if self.fps_min_for_thresholds <= 0.0 or self.fps_max_for_thresholds < self.fps_min_for_thresholds:
            raise ValueError("FPS threshold bounds are invalid.")
        if not 0.0 < self.fps_ema_alpha <= 1.0:
            raise ValueError("fps_ema_alpha must be in (0.0, 1.0].")
        if self.blink_debug_log_interval_s < 0.0:
            raise ValueError("blink_debug_log_interval_s cannot be negative.")
        if self.double_long_blink_window_ms <= 0.0:
            raise ValueError("double_long_blink_window_ms must be positive.")
        if self.gesture_display_ms < 0.0 or self.gesture_cooldown_ms < 0.0:
            raise ValueError("gesture timing values cannot be negative.")
        if self.gesture_cooldown_ms < self.gesture_display_ms:
            raise ValueError("gesture_cooldown_ms must be >= gesture_display_ms.")
        if self.action_cooldown_ms < 0.0:
            raise ValueError("action_cooldown_ms cannot be negative.")
        if self.action_cooldown_ms < self.gesture_display_ms:
            raise ValueError("action_cooldown_ms must be >= gesture_display_ms.")
        if not 0.0 < self.gaze_smoothing_alpha <= 1.0:
            raise ValueError("gaze_smoothing_alpha must be in (0.0, 1.0].")
        if self.cursor_sensitivity <= 0.0:
            raise ValueError("cursor_sensitivity must be positive.")
        if not 0.0 < self.cursor_smoothing_alpha <= 1.0:
            raise ValueError("cursor_smoothing_alpha must be in (0.0, 1.0].")
        if self.cursor_dead_zone_px < 0.0:
            raise ValueError("cursor_dead_zone_px cannot be negative.")
        if self.cursor_min_move_px < 0.0:
            raise ValueError("cursor_min_move_px cannot be negative.")
        if self.cursor_edge_padding_px < 0:
            raise ValueError("cursor_edge_padding_px cannot be negative.")
        if self.cursor_move_duration_seconds < 0.0:
            raise ValueError("cursor_move_duration_seconds cannot be negative.")
        if self.cursor_max_step_px <= 0.0:
            raise ValueError("cursor_max_step_px must be positive.")
        if self.cursor_recovery_frames < 0:
            raise ValueError("cursor_recovery_frames cannot be negative.")
        if self.kinematic_mass <= 0.0:
            raise ValueError("kinematic_mass must be positive.")
        if self.kinematic_stiffness <= 0.0:
            raise ValueError("kinematic_stiffness must be positive.")
        if self.kinematic_damping_ratio <= 0.0:
            raise ValueError("kinematic_damping_ratio must be positive.")
        if self.kinematic_damping <= 0.0:
            raise ValueError("kinematic_damping must be positive.")
        if self.kinematic_tremor_reduction_px < 0.0:
            raise ValueError("kinematic_tremor_reduction_px cannot be negative.")
        if self.kinematic_deadband_radius < 0.0:
            raise ValueError("kinematic_deadband_radius cannot be negative.")
        if self.kinematic_breakout_radius < self.kinematic_deadband_radius:
            raise ValueError("kinematic_breakout_radius must be >= kinematic_deadband_radius.")
        if self.kinematic_anchor_velocity_threshold < 0.0:
            raise ValueError("kinematic_anchor_velocity_threshold cannot be negative.")
        if self.kinematic_acceleration_gain < 0.0:
            raise ValueError("kinematic_acceleration_gain cannot be negative.")
        if self.kinematic_max_velocity_px_s <= 0.0:
            raise ValueError("kinematic_max_velocity_px_s must be positive.")
        if self.gaze_gain_x <= 0.0 or self.gaze_gain_y <= 0.0:
            raise ValueError("gaze_gain_x and gaze_gain_y must be positive.")
        if not 0.0 <= self.gaze_neutral_x <= 1.0 or not 0.0 <= self.gaze_neutral_y <= 1.0:
            raise ValueError("gaze_neutral_x and gaze_neutral_y must be in [0.0, 1.0].")
        if self.gaze_vertical_deadzone < 0.0:
            raise ValueError("gaze_vertical_deadzone cannot be negative.")
        if not 0.0 <= self.tracking_confidence_threshold <= 1.0:
            raise ValueError("tracking_confidence_threshold must be in [0.0, 1.0].")
        if self.calibration_stabilize_ms < 0.0:
            raise ValueError("calibration_stabilize_ms cannot be negative.")
        if self.calibration_sample_count < 1:
            raise ValueError("calibration_sample_count must be at least 1.")
        if self.calibration_sample_timeout_ms <= 0.0:
            raise ValueError("calibration_sample_timeout_ms must be positive.")
        if self.calibration_sample_poll_ms <= 0.0:
            raise ValueError("calibration_sample_poll_ms must be positive.")
        if self.calibration_min_valid_samples < 1:
            raise ValueError("calibration_min_valid_samples must be at least 1.")
        if self.calibration_min_valid_samples > self.calibration_sample_count:
            raise ValueError(
                "calibration_min_valid_samples cannot exceed calibration_sample_count."
            )
        if self.calibration_outlier_mad_scale <= 0.0:
            raise ValueError("calibration_outlier_mad_scale must be positive.")
        if self.calibration_max_center_jump <= 0.0:
            raise ValueError("calibration_max_center_jump must be positive.")
        if self.calibration_max_sample_dispersion <= 0.0:
            raise ValueError("calibration_max_sample_dispersion must be positive.")
        if not 0.0 < self.calibration_quality_threshold <= 1.0:
            raise ValueError("calibration_quality_threshold must be in (0.0, 1.0].")
        if self.calibration_rmse_scale <= 0.0:
            raise ValueError("calibration_rmse_scale must be positive.")
        if not self.calibration_quality_threshold <= self.calibration_good_score_threshold <= 1.0:
            raise ValueError(
                "calibration_good_score_threshold must be in "
                "[calibration_quality_threshold, 1.0]."
            )
        if self.validation_mean_norm_threshold <= 0.0 or self.validation_mean_norm_threshold > 1.0:
            raise ValueError("validation_mean_norm_threshold must be in (0.0, 1.0].")
        if self.validation_max_norm_threshold <= 0.0 or self.validation_max_norm_threshold > 1.0:
            raise ValueError("validation_max_norm_threshold must be in (0.0, 1.0].")
        if self.validation_max_norm_threshold < self.validation_mean_norm_threshold:
            raise ValueError("validation_max_norm_threshold must be >= validation_mean_norm_threshold.")
        if self.calibration_max_condition_number <= 0.0:
            raise ValueError("calibration_max_condition_number must be positive.")
        if self.calibration_mode not in {"16-point", "9-point"}:
            raise ValueError("calibration_mode must be '16-point' or '9-point'.")
        if self.overlay_mode not in {"normal", "debug"}:
            raise ValueError("overlay_mode must be 'normal' or 'debug'.")


def default_eye_interaction_config() -> EyeInteractionConfig:
    """Return the validated default configuration."""
    config = EyeInteractionConfig()
    config.validate()
    return config


def build_eye_interaction_config() -> EyeInteractionConfig:
    """Build shared eye interaction thresholds from application settings."""
    config = EyeInteractionConfig(
        ear_close_threshold=settings.EAR_CLOSE_THRESHOLD,
        ear_open_threshold=settings.EAR_OPEN_THRESHOLD,
        ear_freeze_threshold=getattr(settings, "EAR_FREEZE_THRESHOLD", 0.19),
        ear_recovery_threshold=getattr(settings, "EAR_OPEN_THRESHOLD", 0.21),
        ear_click_threshold=getattr(settings, "EAR_CLOSE_THRESHOLD", 0.16),
        cursor_history_buffer_maxlen=6,
        intentional_blink_min_ms=settings.INTENTIONAL_BLINK_MIN_MS,
        intentional_blink_max_ms=settings.INTENTIONAL_BLINK_MAX_MS,
        double_long_blink_window_ms=settings.DOUBLE_LONG_BLINK_WINDOW_MS,
        kinematic_physics_enabled=getattr(settings, "KINEMATIC_PHYSICS_ENABLED", True),
        kinematic_stiffness=getattr(settings, "KINEMATIC_STIFFNESS", 160.0),
        kinematic_damping=getattr(settings, "KINEMATIC_DAMPING", 25.3),
        kinematic_damping_ratio=getattr(settings, "KINEMATIC_DAMPING_RATIO", 1.0),
        kinematic_mass=getattr(settings, "KINEMATIC_MASS", 1.0),
        kinematic_tremor_reduction_px=getattr(settings, "KINEMATIC_TREMOR_REDUCTION_PX", 14.0),
        kinematic_deadband_radius=getattr(settings, "KINEMATIC_DEADBAND_RADIUS", 18.0),
        kinematic_breakout_radius=getattr(settings, "KINEMATIC_BREAKOUT_RADIUS", 25.0),
        kinematic_anchor_velocity_threshold=getattr(settings, "KINEMATIC_ANCHOR_VELOCITY_THRESHOLD", 15.0),
        kinematic_acceleration_gain=getattr(settings, "KINEMATIC_ACCELERATION_GAIN", 1.5),
        kinematic_max_velocity_px_s=getattr(settings, "KINEMATIC_MAX_VELOCITY_PX_S", 12000.0),
        gaze_gain_x=getattr(settings, "GAZE_GAIN_X", 3.6),
        gaze_gain_y=getattr(settings, "GAZE_GAIN_Y", 3.2),
        gaze_neutral_x=getattr(settings, "GAZE_NEUTRAL_X", 0.50),
        gaze_neutral_y=getattr(settings, "GAZE_NEUTRAL_Y", 0.70),
        gaze_vertical_deadzone=getattr(settings, "GAZE_VERTICAL_DEADZONE", 0.0),
        cursor_sensitivity=settings.CURSOR_SENSITIVITY,
        cursor_smoothing_alpha=settings.CURSOR_SMOOTHING,
        cursor_dead_zone_px=settings.CURSOR_DEAD_ZONE_PX,
        cursor_min_move_px=settings.CURSOR_MIN_MOVE_PX,
        cursor_max_step_px=settings.CURSOR_MAX_STEP_PX,
        gaze_smoothing_alpha=settings.GAZE_SMOOTHING,
        tracking_confidence_threshold=settings.TRACKING_CONFIDENCE_THRESHOLD,
        calibration_quality_threshold=settings.CALIBRATION_QUALITY_THRESHOLD,
        calibration_rmse_scale=settings.CALIBRATION_RMSE_SCALE,
        calibration_good_score_threshold=settings.CALIBRATION_GOOD_SCORE_THRESHOLD,
        overlay_mode=settings.OVERLAY_MODE.lower().strip(),
    )
    config.validate()
    return config
