"""Stateful selection manager for gaze and cursor text/element selection."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
import time

from backend.automation.controller import DesktopController
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class SelectionState:
    """Current state of text or screen element selection."""

    is_selecting: bool
    anchor_x: float | None = None
    anchor_y: float | None = None
    current_x: float | None = None
    current_y: float | None = None
    start_time: float | None = None


class SelectionManager:
    """Manages stateful selection workflows ("Start selecting" ... "Stop selecting")."""

    def __init__(self, desktop_controller: DesktopController) -> None:
        self._desktop_controller = desktop_controller
        self._is_selecting = False
        self._anchor_x: float | None = None
        self._anchor_y: float | None = None
        self._current_x: float | None = None
        self._current_y: float | None = None
        self._start_time: float | None = None
        self._lock = RLock()

    def get_state(self) -> SelectionState:
        with self._lock:
            return SelectionState(
                is_selecting=self._is_selecting,
                anchor_x=self._anchor_x,
                anchor_y=self._anchor_y,
                current_x=self._current_x,
                current_y=self._current_y,
                start_time=self._start_time,
            )

    def start_selection(self, x: float | None = None, y: float | None = None) -> bool:
        """Begin stateful selection anchor at current position or target (x, y)."""
        with self._lock:
            self._is_selecting = True
            self._anchor_x = x
            self._anchor_y = y
            self._current_x = x
            self._current_y = y
            self._start_time = time.time()
            if x is not None and y is not None:
                self._desktop_controller.move_rel(int(x), int(y))
            logger.info("Selection started at anchor (x=%s, y=%s)", x, y)
            return True

    def update_position(self, x: float, y: float) -> None:
        """Update active selection cursor position."""
        with self._lock:
            if not self._is_selecting:
                return
            self._current_x = x
            self._current_y = y
            self._desktop_controller.move_rel(int(x), int(y))

    def stop_selection(self, end_x: float | None = None, end_y: float | None = None) -> bool:
        """Complete stateful selection drag."""
        with self._lock:
            if not self._is_selecting:
                return False
            if end_x is not None and end_y is not None:
                self._desktop_controller.move_rel(int(end_x), int(end_y))
            self._is_selecting = False
            logger.info("Selection completed.")
            return True
