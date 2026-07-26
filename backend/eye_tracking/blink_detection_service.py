"""Intentional long-blink detection from MediaPipe eye landmarks.

Natural blinks (typically under ~450 ms) are tracked for eye-open state but
never emitted as blink events. Only held blinks inside the configured
intentional window produce events for the gesture layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from threading import RLock
from time import monotonic

from backend.eye_tracking.eye_interaction_config import (
    EyeInteractionConfig,
    default_eye_interaction_config,
)
from backend.eye_tracking.face_mesh_service import EyeData, NormalizedLandmark
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class BlinkState:
    """Latest blink detection state for downstream gesture interpretation."""

    leftEyeOpen: bool
    rightEyeOpen: bool
    leftBlink: bool
    rightBlink: bool
    bothBlink: bool
    intentionalBlink: bool
    blinkDurationMs: float
    holdActive: bool
    holdProgress: float
    holdDurationMs: float
    leftEar: float | None
    rightEar: float | None
    smoothedLeftEar: float | None
    smoothedRightEar: float | None
    smoothedEar: float | None
    closedFrames: int
    openFrames: int
    measuredFps: float
    updatedAt: float


@dataclass
class _EyeTemporalState:
    """Per-eye temporal filter for intentional blink detection."""

    open: bool = True
    closed_frames: int = 0
    open_frames: int = 0
    closed_since: float | None = None
    last_intentional_blink_at: float | None = None
    last_intentional_duration_ms: float = 0.0
    smoothed_ear: float | None = None


@dataclass
class _PendingUnilateralBlink:
    """Single-eye intentional blink waiting to coalesce into both-eyes."""

    eye: str
    duration_ms: float
    timestamp: float


class BlinkDetectionService:
    """Detect intentional long blinks while ignoring natural blinks.

    MediaPipe Face Mesh EAR landmarks (Soukupova & Cech ordering):
    right ``(33, 160, 158, 133, 153, 144)``,
    left ``(362, 385, 387, 263, 373, 380)``.
    """

    _RIGHT_EAR_INDICES = (33, 160, 158, 133, 153, 144)
    _LEFT_EAR_INDICES = (362, 385, 387, 263, 373, 380)

    def __init__(self, config: EyeInteractionConfig | None = None) -> None:
        """Create a blink detector from the shared eye interaction config."""
        self._config = config or default_eye_interaction_config()
        self._config.validate()
        self._left = _EyeTemporalState()
        self._right = _EyeTemporalState()
        self._pending_unilateral: _PendingUnilateralBlink | None = None
        self._frame_interval_ema: float | None = None
        self._last_frame_at: float | None = None
        self._measured_fps = 30.0
        self._last_debug_log_at = 0.0
        self._hold_click_emitted = False
        self._latest_state = self._empty_state(updated_at=monotonic())
        self._lock = RLock()

    def update(self, eye_data: EyeData | None) -> BlinkState:
        """Update blink detection from the latest eye landmarks."""
        now = monotonic()
        self._update_fps(now)

        if eye_data is None:
            with self._lock:
                self._reset_temporal_state()
                self._latest_state = self._empty_state(
                    left_eye_open=False,
                    right_eye_open=False,
                    updated_at=now,
                )
                return self._latest_state

        try:
            raw_left = self._calculate_ear(eye_data.left_eye, self._LEFT_EAR_INDICES)
            raw_right = self._calculate_ear(eye_data.right_eye, self._RIGHT_EAR_INDICES)
        except ValueError as exc:
            logger.warning("Skipping blink detection for invalid eye data: %s", exc)
            return self.update(None)

        with self._lock:
            left_ear = self._smooth_ear(self._left, raw_left)
            right_ear = self._smooth_ear(self._right, raw_right)
            closed_frames_needed, open_frames_needed = self._adaptive_frame_thresholds()

            left_event, left_duration = self._update_eye_state(
                self._left,
                left_ear,
                now,
                closed_frames_needed,
                open_frames_needed,
            )
            right_event, right_duration = self._update_eye_state(
                self._right,
                right_ear,
                now,
                closed_frames_needed,
                open_frames_needed,
            )
            left_blink, right_blink, both_blink, blink_duration_ms = self._coalesce_blink_events(
                left_event=left_event,
                left_duration=left_duration,
                right_event=right_event,
                right_duration=right_duration,
                now=now,
            )
            hold_active, hold_progress, hold_duration_ms, threshold_click = self._update_hold_progress(
                now=now
            )
            if threshold_click:
                both_blink = True
                blink_duration_ms = hold_duration_ms
            intentional = both_blink or left_blink or right_blink or threshold_click
            smoothed_ear = (left_ear + right_ear) / 2.0
            closed_frames = max(self._left.closed_frames, self._right.closed_frames)
            open_frames = max(self._left.open_frames, self._right.open_frames)

            self._latest_state = BlinkState(
                leftEyeOpen=self._left.open,
                rightEyeOpen=self._right.open,
                leftBlink=left_blink,
                rightBlink=right_blink,
                bothBlink=both_blink,
                intentionalBlink=intentional,
                blinkDurationMs=blink_duration_ms,
                holdActive=hold_active,
                holdProgress=hold_progress,
                holdDurationMs=hold_duration_ms,
                leftEar=raw_left,
                rightEar=raw_right,
                smoothedLeftEar=left_ear,
                smoothedRightEar=right_ear,
                smoothedEar=smoothed_ear,
                closedFrames=closed_frames,
                openFrames=open_frames,
                measuredFps=self._measured_fps,
                updatedAt=now,
            )

            if intentional:
                logger.info(
                    "blink intentional duration_ms=%.0f both=%s fps=%.1f",
                    blink_duration_ms,
                    both_blink,
                    self._measured_fps,
                )
            elif now - self._last_debug_log_at >= self._config.blink_debug_log_interval_s:
                self._last_debug_log_at = now
                logger.debug(
                    "blink ear_l=%.3f ear_r=%.3f smoothed=%.3f open_l=%s open_r=%s fps=%.1f",
                    raw_left,
                    raw_right,
                    smoothed_ear,
                    self._left.open,
                    self._right.open,
                    self._measured_fps,
                )
            return self._latest_state

    def get_latest_state(self) -> BlinkState:
        """Return the latest blink detection state."""
        with self._lock:
            return self._latest_state

    def reset(self) -> BlinkState:
        """Clear temporal filter state and return an open-eye state."""
        with self._lock:
            self._reset_temporal_state()
            self._frame_interval_ema = None
            self._last_frame_at = None
            self._measured_fps = 30.0
            self._latest_state = self._empty_state(updated_at=monotonic())
            logger.info("Blink detection state reset.")
            return self._latest_state

    def _update_fps(self, now: float) -> None:
        """Track measured pipeline FPS from inter-frame intervals."""
        if self._last_frame_at is not None:
            interval = max(now - self._last_frame_at, 1e-4)
            alpha = self._config.fps_ema_alpha
            if self._frame_interval_ema is None:
                self._frame_interval_ema = interval
            else:
                self._frame_interval_ema = alpha * interval + (1.0 - alpha) * self._frame_interval_ema
            self._measured_fps = max(1.0 / self._frame_interval_ema, 1.0)
        self._last_frame_at = now

    def _adaptive_frame_thresholds(self) -> tuple[int, int]:
        """Scale closed/open confirmation frames with measured FPS."""
        fps = min(
            max(self._measured_fps, self._config.fps_min_for_thresholds),
            self._config.fps_max_for_thresholds,
        )
        closed = max(
            self._config.closed_frames_min,
            min(
                self._config.closed_frames_max,
                int(round(fps * self._config.fps_closed_seconds)),
            ),
        )
        opened = max(
            self._config.open_frames_min,
            min(
                self._config.open_frames_max,
                int(round(fps * self._config.fps_open_seconds)),
            ),
        )
        return closed, opened

    def _smooth_ear(self, state: _EyeTemporalState, raw_ear: float) -> float:
        """EMA-smooth EAR to reduce webcam landmark jitter."""
        alpha = self._config.ear_smoothing_alpha
        if state.smoothed_ear is None:
            state.smoothed_ear = raw_ear
        else:
            state.smoothed_ear = alpha * raw_ear + (1.0 - alpha) * state.smoothed_ear
        return state.smoothed_ear

    def _update_eye_state(
        self,
        state: _EyeTemporalState,
        ear: float,
        now: float,
        closed_frames_needed: int,
        open_frames_needed: int,
    ) -> tuple[bool, float]:
        """Update one eye and emit an intentional blink event when warranted."""
        blink = False
        blink_duration_ms = 0.0
        eye_is_closed = self._is_eye_closed(state, ear)

        if eye_is_closed:
            if state.closed_since is None:
                state.closed_since = now
            state.closed_frames += 1
            state.open_frames = 0
            if state.open and state.closed_frames >= closed_frames_needed:
                state.open = False
        else:
            state.open_frames += 1
            state.closed_frames = 0

            if not state.open and state.open_frames >= open_frames_needed:
                blink_duration_ms = self._finalize_blink_duration(state, now)
                state.open = True
                state.closed_since = None

                # Prefer threshold-fire while closed; only emit on open if the
                # hold never reached the intentional minimum (legacy path).
                if (
                    not self._hold_click_emitted
                    and self._is_intentional_blink(blink_duration_ms)
                ):
                    blink = True
                    state.last_intentional_blink_at = now
                    state.last_intentional_duration_ms = blink_duration_ms
                else:
                    blink_duration_ms = 0.0
            elif state.open:
                state.closed_since = None
                state.open_frames = 0

        return blink, blink_duration_ms

    def _update_hold_progress(self, now: float) -> tuple[bool, float, float, bool]:
        """Track closed-eye hold progress and fire when the min threshold is hit.

        Progress resets immediately if either eye reopens before the threshold.
        """
        both_closed = (not self._left.open) and (not self._right.open)
        if not both_closed:
            if self._left.open and self._right.open:
                self._hold_click_emitted = False
            return False, 0.0, 0.0, False

        closed_times = [
            stamp
            for stamp in (self._left.closed_since, self._right.closed_since)
            if stamp is not None
        ]
        if not closed_times:
            return False, 0.0, 0.0, False

        hold_duration_ms = max((now - min(closed_times)) * 1000.0, 0.0)
        min_ms = self._config.intentional_blink_min_ms
        max_ms = self._config.intentional_blink_max_ms
        progress = min(hold_duration_ms / min_ms, 1.0) if min_ms > 0 else 0.0

        threshold_click = False
        if (
            not self._hold_click_emitted
            and min_ms <= hold_duration_ms <= max_ms
        ):
            self._hold_click_emitted = True
            threshold_click = True
            self._left.last_intentional_blink_at = now
            self._right.last_intentional_blink_at = now
            self._left.last_intentional_duration_ms = hold_duration_ms
            self._right.last_intentional_duration_ms = hold_duration_ms
            logger.info(
                "blink hold threshold reached duration_ms=%.0f progress=1.0",
                hold_duration_ms,
            )

        return True, progress, hold_duration_ms, threshold_click

    def _is_eye_closed(self, state: _EyeTemporalState, ear: float) -> bool:
        """Apply EAR hysteresis so open/closed transitions stay stable."""
        if state.open:
            return ear < self._config.ear_close_threshold
        return ear < self._config.ear_open_threshold

    def _is_intentional_blink(self, duration_ms: float) -> bool:
        """Return whether closed duration matches an intentional long blink."""
        return (
            self._config.intentional_blink_min_ms
            <= duration_ms
            <= self._config.intentional_blink_max_ms
        )

    def _coalesce_blink_events(
        self,
        left_event: bool,
        left_duration: float,
        right_event: bool,
        right_duration: float,
        now: float,
    ) -> tuple[bool, bool, bool, float]:
        """Merge staggered intentional single-eye events into both-eye blinks."""
        left_blink = False
        right_blink = False
        both_blink = False
        blink_duration_ms = 0.0

        if left_event and right_event:
            return False, False, True, max(left_duration, right_duration)

        if left_event or right_event:
            eye = "left" if left_event else "right"
            duration = left_duration if left_event else right_duration
            other_state = self._right if eye == "left" else self._left

            if self._pending_unilateral is not None:
                pending = self._pending_unilateral
                delta_ms = (now - pending.timestamp) * 1000.0
                if pending.eye != eye and delta_ms <= self._config.both_eye_coalesce_ms:
                    self._pending_unilateral = None
                    return False, False, True, max(duration, pending.duration_ms)
                left_blink, right_blink, blink_duration_ms = self._emit_pending_unilateral()

            if not other_state.open:
                self._pending_unilateral = _PendingUnilateralBlink(
                    eye=eye,
                    duration_ms=duration,
                    timestamp=now,
                )
            elif eye == "left":
                left_blink = True
                blink_duration_ms = max(blink_duration_ms, duration)
            else:
                right_blink = True
                blink_duration_ms = max(blink_duration_ms, duration)

            if left_blink and right_blink:
                return False, False, True, max(left_duration, right_duration, blink_duration_ms)
            return left_blink, right_blink, both_blink, blink_duration_ms

        if self._pending_unilateral is not None:
            elapsed_ms = (now - self._pending_unilateral.timestamp) * 1000.0
            if elapsed_ms > self._config.both_eye_coalesce_ms:
                left_blink, right_blink, blink_duration_ms = self._emit_pending_unilateral()

        return left_blink, right_blink, both_blink, blink_duration_ms

    def _emit_pending_unilateral(self) -> tuple[bool, bool, float]:
        """Emit and clear a deferred single-eye intentional blink."""
        pending = self._pending_unilateral
        self._pending_unilateral = None
        if pending is None:
            return False, False, 0.0
        if pending.eye == "left":
            return True, False, pending.duration_ms
        return False, True, pending.duration_ms

    def _calculate_ear(
        self,
        landmarks: tuple[NormalizedLandmark, ...],
        indices: tuple[int, int, int, int, int, int],
    ) -> float:
        """Calculate Eye Aspect Ratio for one eye from indexed landmarks."""
        points = {landmark.index: landmark for landmark in landmarks}
        try:
            p1, p2, p3, p4, p5, p6 = (points[index] for index in indices)
        except KeyError as exc:
            raise ValueError(f"missing EAR landmark index {exc.args[0]}") from exc

        vertical_1 = hypot(p2.x - p6.x, p2.y - p6.y)
        vertical_2 = hypot(p3.x - p5.x, p3.y - p5.y)
        horizontal = hypot(p1.x - p4.x, p1.y - p4.y)
        if horizontal <= 0.0:
            raise ValueError("horizontal eye distance is zero")

        ear = (vertical_1 + vertical_2) / (2.0 * horizontal)
        if not isfinite(ear):
            raise ValueError("EAR is not finite")
        return ear

    def _finalize_blink_duration(self, state: _EyeTemporalState, now: float) -> float:
        """Measure closed-eye duration from the first closed frame."""
        if state.closed_since is None:
            return 0.0
        return max((now - state.closed_since) * 1000.0, 0.0)

    def _reset_temporal_state(self) -> None:
        """Reset per-eye filters and pending coalesce state."""
        self._left = _EyeTemporalState()
        self._right = _EyeTemporalState()
        self._pending_unilateral = None
        self._hold_click_emitted = False

    def _empty_state(
        self,
        *,
        left_eye_open: bool = True,
        right_eye_open: bool = True,
        updated_at: float | None = None,
    ) -> BlinkState:
        """Build a neutral blink state."""
        return BlinkState(
            leftEyeOpen=left_eye_open,
            rightEyeOpen=right_eye_open,
            leftBlink=False,
            rightBlink=False,
            bothBlink=False,
            intentionalBlink=False,
            blinkDurationMs=0.0,
            holdActive=False,
            holdProgress=0.0,
            holdDurationMs=0.0,
            leftEar=None,
            rightEar=None,
            smoothedLeftEar=None,
            smoothedRightEar=None,
            smoothedEar=None,
            closedFrames=0,
            openFrames=0,
            measuredFps=self._measured_fps,
            updatedAt=updated_at if updated_at is not None else monotonic(),
        )
