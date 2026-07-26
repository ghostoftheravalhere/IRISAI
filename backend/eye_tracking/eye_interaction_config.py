"""Central configuration for the eye interaction pipeline.

All EAR, blink, gesture, cursor, and calibration thresholds live here so
accessibility behavior can be tuned without hunting through services.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EyeInteractionConfig:
    """Production thresholds for intentional eye interaction.

    Natural blinks are ignored. Only held (intentional) blinks in the
    configured duration window produce gestures.
    """

    # --- EAR classification ---
    ear_close_threshold: float = 0.21
    ear_open_threshold: float = 0.26
    ear_smoothing_alpha: float = 0.35

    # --- Intentional blink timing (milliseconds) ---
    # Natural blinks are typically 100–400 ms and must never click.
    # Demo window is widened so judges can reliably hold a long blink.
    intentional_blink_min_ms: float = 500.0
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
    # Lower EMA alphas = heavier smoothing (less noisy, modest added lag).
    gaze_smoothing_alpha: float = 0.28
    cursor_sensitivity: float = 0.92
    cursor_smoothing_alpha: float = 0.12
    cursor_dead_zone_px: float = 28.0
    cursor_min_move_px: float = 2.5
    cursor_edge_padding_px: int = 8
    cursor_move_duration_seconds: float = 0.0
    cursor_max_step_px: float = 48.0
    cursor_recovery_frames: int = 6
    tracking_confidence_threshold: float = 0.45

    # --- Calibration sampling ---
    # Wait for gaze to settle, then average many frames so one noisy frame
    # cannot dominate the affine fit.
    calibration_stabilize_ms: float = 250.0
    calibration_sample_count: int = 25
    calibration_sample_timeout_ms: float = 4000.0
    calibration_sample_poll_ms: float = 20.0
    calibration_min_valid_samples: int = 12
    # Reject frames whose eye-center MAD exceeds this robust z-score.
    calibration_outlier_mad_scale: float = 2.5
    # Reject consecutive samples with sudden head / landmark jumps.
    calibration_max_center_jump: float = 0.035
    # Reject a capture whose inlier gaze cloud is still too spread out
    # (user still settling / head moving). Units: normalized face space.
    calibration_max_sample_dispersion: float = 0.012

    # --- Calibration quality ---
    # RMSE / score math is unchanged. These thresholds only classify usability
    # for webcam eyelid-landmark affine fits (not optical eye trackers).
    #
    # Score = 1 / (1 + rmse * 5). Typical careful webcam residual RMSE ≈ 0.10–0.20
    # (score ≈ 0.67–0.50) while the cursor remains practically usable.
    #   Good  >= 0.58  → RMSE <= ~0.145  (solid for a webcam)
    #   Fair  >= 0.45  → RMSE <= ~0.244  (usable; corners softer)
    #   Poor  <  0.45  → recalibrate / block cursor enable
    calibration_quality_threshold: float = 0.45
    calibration_rmse_scale: float = 5.0
    calibration_good_score_threshold: float = 0.58

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
        if self.overlay_mode not in {"normal", "debug"}:
            raise ValueError("overlay_mode must be 'normal' or 'debug'.")


def default_eye_interaction_config() -> EyeInteractionConfig:
    """Return the validated default configuration."""
    config = EyeInteractionConfig()
    config.validate()
    return config
