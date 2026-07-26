"""Gesture interpretation for intentional long blinks only.

Natural blinks never reach this service as events. The state machine only
emits ``LONG_BLINK`` and ``DOUBLE_LONG_BLINK``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import RLock
from time import monotonic

from backend.eye_tracking.blink_detection_service import BlinkState
from backend.eye_tracking.eye_interaction_config import (
    EyeInteractionConfig,
    default_eye_interaction_config,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GestureType(str, Enum):
    """Supported intentional eye gesture types."""

    LONG_BLINK = "LONG_BLINK"
    DOUBLE_LONG_BLINK = "DOUBLE_LONG_BLINK"
    NO_GESTURE = "NO_GESTURE"


class _InterpreterMode(str, Enum):
    """Internal gesture state machine modes."""

    IDLE = "IDLE"
    WAITING_SECOND_BLINK = "WAITING_SECOND_BLINK"
    DISPLAY = "DISPLAY"
    COOLDOWN = "COOLDOWN"


@dataclass(frozen=True)
class GestureState:
    """Latest interpreted gesture state."""

    gesture: GestureType
    timestamp: float | None
    sourceBlinkTimestamp: float | None
    cooldownActive: bool


@dataclass(frozen=True)
class _PendingBlink:
    """First intentional blink waiting for a possible double long blink."""

    timestamp: float
    source_timestamp: float


class GestureInterpreterService:
    """State-machine interpreter for intentional blink gestures.

    This service only interprets blink state. It does not perform clicks,
    cursor movement, desktop automation, or any other side effects.
    """

    def __init__(self, config: EyeInteractionConfig | None = None) -> None:
        """Create a gesture interpreter from the shared eye interaction config."""
        self._config = config or default_eye_interaction_config()
        self._config.validate()
        self._mode = _InterpreterMode.IDLE
        self._pending_blink: _PendingBlink | None = None
        self._display_until: float | None = None
        self._cooldown_until: float | None = None
        self._last_source_timestamp: float | None = None
        self._latest_state = self._build_state(GestureType.NO_GESTURE)
        self._lock = RLock()

    def update(self, blink_state: BlinkState | None) -> GestureState:
        """Update the interpreter from blink detection state."""
        now = monotonic()
        if blink_state is None:
            with self._lock:
                return self._advance_and_emit(now)

        with self._lock:
            self._advance_timers(now)

            if self._mode in {_InterpreterMode.DISPLAY, _InterpreterMode.COOLDOWN}:
                return self._latest_state

            if not self._is_new_intentional_blink(blink_state):
                return self._handle_no_blink_event(now)

            self._last_source_timestamp = blink_state.updatedAt

            # MVP: fire a single long-blink click immediately. Double-long-blink
            # is disabled for hackathon reliability (timing was unreachable).
            return self._fire_gesture(
                gesture=GestureType.LONG_BLINK,
                now=now,
                source_timestamp=blink_state.updatedAt,
            )

    def get_latest_state(self) -> GestureState:
        """Return the latest interpreted gesture state."""
        with self._lock:
            return self._latest_state

    def reset(self) -> GestureState:
        """Reset gesture state machine and return a no-gesture state."""
        with self._lock:
            self._mode = _InterpreterMode.IDLE
            self._pending_blink = None
            self._display_until = None
            self._cooldown_until = None
            self._last_source_timestamp = None
            self._latest_state = self._build_state(GestureType.NO_GESTURE)
            logger.info("Gesture interpreter state reset.")
            return self._latest_state

    def _is_new_intentional_blink(self, blink_state: BlinkState) -> bool:
        """Return whether blink state contains a fresh intentional blink event."""
        if not blink_state.intentionalBlink:
            return False
        if blink_state.updatedAt == self._last_source_timestamp:
            return False
        return True

    def _advance_timers(self, now: float) -> None:
        """Advance display and cooldown timers."""
        if self._mode == _InterpreterMode.DISPLAY:
            if self._display_until is not None and now >= self._display_until:
                self._mode = _InterpreterMode.COOLDOWN
                self._display_until = None
                if self._cooldown_until is None or now >= self._cooldown_until:
                    self._mode = _InterpreterMode.IDLE
                    self._cooldown_until = None
                    self._latest_state = self._build_state(GestureType.NO_GESTURE)
                else:
                    # Keep gesture visible label until display ends; then clear
                    # while remaining in cooldown to block duplicates.
                    self._latest_state = self._build_state(
                        GestureType.NO_GESTURE,
                        cooldown_active=True,
                    )
            return

        if self._mode == _InterpreterMode.COOLDOWN:
            if self._cooldown_until is not None and now >= self._cooldown_until:
                self._mode = _InterpreterMode.IDLE
                self._cooldown_until = None
                self._latest_state = self._build_state(GestureType.NO_GESTURE)

    def _advance_and_emit(self, now: float) -> GestureState:
        """Advance timers when eye data is missing."""
        self._advance_timers(now)
        if self._mode == _InterpreterMode.WAITING_SECOND_BLINK:
            return self._handle_no_blink_event(now)
        return self._latest_state

    def _handle_no_blink_event(self, now: float) -> GestureState:
        """Emit a pending long blink once the double window expires."""
        if self._mode != _InterpreterMode.WAITING_SECOND_BLINK:
            return self._hold_or_idle()

        if self._pending_blink is None or self._is_within_double_window(now):
            return self._hold_or_idle()

        source = self._pending_blink.source_timestamp
        return self._fire_gesture(
            gesture=GestureType.LONG_BLINK,
            now=now,
            source_timestamp=source,
        )

    def _fire_gesture(
        self,
        gesture: GestureType,
        now: float,
        source_timestamp: float | None,
    ) -> GestureState:
        """Emit one gesture, show it for debugging, then enter cooldown."""
        self._mode = _InterpreterMode.DISPLAY
        self._pending_blink = None
        self._display_until = now + self._config.gesture_display_ms / 1000.0
        self._cooldown_until = now + self._config.gesture_cooldown_ms / 1000.0
        self._latest_state = self._build_state(
            gesture=gesture,
            timestamp=now,
            source_timestamp=source_timestamp,
            cooldown_active=True,
        )
        logger.info("gesture recognized=%s", gesture.value)
        return self._latest_state

    def _hold_or_idle(self) -> GestureState:
        """Return current state without fabricating a new gesture."""
        return self._latest_state

    def _is_within_double_window(self, now: float) -> bool:
        """Return whether the pending blink can still become a double long blink."""
        if self._pending_blink is None:
            return False
        elapsed_ms = (now - self._pending_blink.timestamp) * 1000.0
        return elapsed_ms <= self._config.double_long_blink_window_ms

    def _build_state(
        self,
        gesture: GestureType,
        timestamp: float | None = None,
        source_timestamp: float | None = None,
        cooldown_active: bool = False,
    ) -> GestureState:
        """Build an immutable gesture state."""
        return GestureState(
            gesture=gesture,
            timestamp=timestamp,
            sourceBlinkTimestamp=source_timestamp,
            cooldownActive=cooldown_active,
        )
