"""Gesture-to-action interpretation for intentional eye interaction."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from time import monotonic

from backend.eye_tracking.eye_interaction_config import (
    EyeInteractionConfig,
    default_eye_interaction_config,
)
from backend.eye_tracking.gesture_interpreter_service import GestureState, GestureType
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ActionType(str, Enum):
    """High-level actions supported by the eye-tracking action engine."""

    LEFT_CLICK = "LEFT_CLICK"
    RIGHT_CLICK = "RIGHT_CLICK"
    DOUBLE_CLICK = "DOUBLE_CLICK"
    TOGGLE_DRAG = "TOGGLE_DRAG"
    PAUSE_CURSOR = "PAUSE_CURSOR"
    RESUME_CURSOR = "RESUME_CURSOR"
    NO_ACTION = "NO_ACTION"


def _default_gesture_mappings() -> dict[GestureType, ActionType]:
    """MVP mapping: intentional long blink → left click only."""
    return {
        GestureType.LONG_BLINK: ActionType.LEFT_CLICK,
    }


@dataclass(frozen=True)
class ActionEngineConfig:
    """Configurable action engine behavior."""

    gesture_mappings: dict[GestureType, ActionType] = field(default_factory=_default_gesture_mappings)
    cooldown_ms: float = 450.0
    display_ms: float = 650.0


@dataclass(frozen=True)
class ActionState:
    """Latest high-level action state."""

    action: ActionType
    timestamp: float | None
    sourceGesture: GestureType
    sourceGestureTimestamp: float | None
    cursorPaused: bool
    dragMode: bool
    cooldownActive: bool


class ActionEngine:
    """Convert interpreted gestures into high-level action state.

    Normal blinks never arrive as gestures, so they map to ``NO_ACTION`` by
    never entering this engine as a fireable event.
    """

    def __init__(
        self,
        config: ActionEngineConfig | None = None,
        eye_config: EyeInteractionConfig | None = None,
    ) -> None:
        """Create an action engine with configurable gesture mappings."""
        shared = eye_config or default_eye_interaction_config()
        shared.validate()
        self._config = config or ActionEngineConfig(
            cooldown_ms=shared.action_cooldown_ms,
            display_ms=shared.gesture_display_ms,
        )
        self._validate_config(self._config)
        self._cursor_paused = False
        self._drag_mode = False
        self._last_source_timestamp: float | None = None
        self._cooldown_until: float | None = None
        self._display_until: float | None = None
        self._latest_state = self._build_state(ActionType.NO_ACTION)
        self._lock = RLock()

    def update(self, gesture_state: GestureState | None) -> ActionState:
        """Convert a gesture state into a deduplicated action state."""
        now = monotonic()
        with self._lock:
            self._advance_timers(now)

            if gesture_state is None or gesture_state.gesture == GestureType.NO_GESTURE:
                return self._latest_state

            if self._is_blocking(now):
                return self._latest_state

            if (
                gesture_state.timestamp is not None
                and gesture_state.timestamp == self._last_source_timestamp
            ):
                return self._latest_state

            mapped_action = self._config.gesture_mappings.get(
                gesture_state.gesture,
                ActionType.NO_ACTION,
            )
            action = self._resolve_stateful_action(mapped_action)
            if action == ActionType.NO_ACTION:
                return self._latest_state

            self._apply_action_state(action)
            self._last_source_timestamp = gesture_state.timestamp
            self._display_until = now + self._config.display_ms / 1000.0
            self._cooldown_until = now + self._config.cooldown_ms / 1000.0
            self._latest_state = self._build_state(
                action=action,
                timestamp=now,
                source_gesture=gesture_state.gesture,
                source_gesture_timestamp=gesture_state.timestamp,
                cooldown_active=True,
            )
            logger.info("action recognized=%s", action.value)
            return self._latest_state

    def get_latest_state(self) -> ActionState:
        """Return the latest action state."""
        with self._lock:
            return self._latest_state

    def reset(self) -> ActionState:
        """Reset action engine state."""
        with self._lock:
            self._cursor_paused = False
            self._drag_mode = False
            self._last_source_timestamp = None
            self._cooldown_until = None
            self._display_until = None
            self._latest_state = self._build_state(ActionType.NO_ACTION)
            logger.info("Action engine state reset.")
            return self._latest_state

    def _advance_timers(self, now: float) -> None:
        """Clear displayed action after the debug display window."""
        if self._display_until is not None and now >= self._display_until:
            self._display_until = None
            self._latest_state = self._build_state(
                ActionType.NO_ACTION,
                cooldown_active=self._is_cooldown_active(now),
            )
        if self._cooldown_until is not None and now >= self._cooldown_until:
            self._cooldown_until = None

    def _is_blocking(self, now: float) -> bool:
        """Return whether new actions should be suppressed."""
        return self._is_cooldown_active(now) or (
            self._display_until is not None and now < self._display_until
        )

    def _resolve_stateful_action(self, action: ActionType) -> ActionType:
        """Resolve toggle-style mappings into concrete state transitions."""
        if action == ActionType.PAUSE_CURSOR and self._cursor_paused:
            return ActionType.RESUME_CURSOR
        if action == ActionType.RESUME_CURSOR and not self._cursor_paused:
            return ActionType.PAUSE_CURSOR
        return action

    def _apply_action_state(self, action: ActionType) -> None:
        """Update action engine state after a fired action."""
        if action == ActionType.PAUSE_CURSOR:
            self._cursor_paused = True
        elif action == ActionType.RESUME_CURSOR:
            self._cursor_paused = False
        elif action == ActionType.TOGGLE_DRAG:
            self._drag_mode = not self._drag_mode

    def _is_cooldown_active(self, now: float) -> bool:
        """Return whether the action cooldown is active."""
        return self._cooldown_until is not None and now < self._cooldown_until

    def _build_state(
        self,
        action: ActionType,
        timestamp: float | None = None,
        source_gesture: GestureType = GestureType.NO_GESTURE,
        source_gesture_timestamp: float | None = None,
        cooldown_active: bool = False,
    ) -> ActionState:
        """Build an immutable action state."""
        return ActionState(
            action=action,
            timestamp=timestamp,
            sourceGesture=source_gesture,
            sourceGestureTimestamp=source_gesture_timestamp,
            cursorPaused=self._cursor_paused,
            dragMode=self._drag_mode,
            cooldownActive=cooldown_active,
        )

    def _validate_config(self, config: ActionEngineConfig) -> None:
        """Validate action engine configuration."""
        if config.cooldown_ms < 0.0:
            raise ValueError("cooldown_ms cannot be negative.")
        if config.display_ms < 0.0:
            raise ValueError("display_ms cannot be negative.")
