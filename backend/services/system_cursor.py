"""Native Win32 OS-Level Cursor Control Engine with DPI awareness and safety boundaries."""

from __future__ import annotations

import sys
import threading
from typing import Any

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Win32 Mouse Event Flags
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040

# Win32 System Metrics Constants
SM_CXSCREEN = 0
SM_CYSCREEN = 1


def set_dpi_awareness() -> bool:
    """Initialize Win32 per-monitor DPI awareness to prevent pixel misalignment."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        # PROCESS_PER_MONITOR_DPI_AWARE = 2
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        logger.info("Set PROCESS_PER_MONITOR_DPI_AWARE (2) successfully.")
        return True
    except Exception as exc_shcore:
        try:
            import ctypes

            ctypes.windll.user32.SetProcessDPIAware()
            logger.info("Fallback SetProcessDPIAware() succeeded.")
            return True
        except Exception as exc_user32:
            logger.warning(
                "Could not set DPI awareness: shcore=%s, user32=%s",
                exc_shcore,
                exc_user32,
            )
            return False


def get_screen_dimensions() -> tuple[int, int]:
    """Dynamically fetch screen width and height using Win32 metrics."""
    if sys.platform == "win32":
        try:
            import ctypes

            width = ctypes.windll.user32.GetSystemMetrics(SM_CXSCREEN)
            height = ctypes.windll.user32.GetSystemMetrics(SM_CYSCREEN)
            if width > 0 and height > 0:
                return (int(width), int(height))
        except Exception as exc:
            logger.warning("Failed to query Win32 screen metrics: %s", exc)

    # Standard fallback
    return (1920, 1080)


class SystemCursor:
    """Native OS-level cursor controller with DPI awareness, bounds clamping, and kill-switch."""

    def __init__(self, enabled: bool = False) -> None:
        self._enabled: bool = enabled
        self._lock: threading.Lock = threading.Lock()
        self._dpi_aware: bool = set_dpi_awareness()

    @property
    def enabled(self) -> bool:
        """Return whether OS cursor hijacking is currently enabled."""
        with self._lock:
            return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Set whether OS cursor hijacking is enabled."""
        with self._lock:
            self._enabled = bool(value)

    @property
    def screen_size(self) -> tuple[int, int]:
        """Return current (width, height) screen dimensions."""
        return get_screen_dimensions()

    def get_cursor_position(self) -> tuple[int, int]:
        """Return actual OS cursor position via native Win32 GetCursorPos."""
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                pt = wintypes.POINT()
                if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
                    return int(pt.x), int(pt.y)
            except Exception:
                pass
        return (0, 0)

    def clamp_coordinates(self, x: float | int, y: float | int) -> tuple[int, int]:
        """Clamp coordinates strictly within valid screen bounds [0, width - 1], [0, height - 1]."""
        width, height = self.screen_size
        max_x = max(0, width - 1)
        max_y = max(0, height - 1)

        clamped_x = max(0, min(int(round(x)), max_x))
        clamped_y = max(0, min(int(round(y)), max_y))
        return (clamped_x, clamped_y)

    def move_cursor(self, x: float | int, y: float | int) -> bool:
        """Move the native OS cursor to clamped (x, y) coordinates if enabled."""
        with self._lock:
            if not self._enabled:
                return False

        clamped_x, clamped_y = self.clamp_coordinates(x, y)

        if not hasattr(self, "_debug_counter"):
            self._debug_counter = 0
        self._debug_counter += 1
        if self._debug_counter % 30 == 0:
            print(f"[SYSTEM CURSOR DEBUG] SetCursorPos -> ({clamped_x}, {clamped_y}) [screen: {self.screen_size[0]}x{self.screen_size[1]}]")

        if sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.user32.SetCursorPos(clamped_x, clamped_y)
                return True
            except Exception as exc:
                logger.error("Failed to execute SetCursorPos(%d, %d): %s", clamped_x, clamped_y, exc)
                return False
        return True

    def click(
        self,
        x: float | int | None = None,
        y: float | int | None = None,
        button: str = "left",
    ) -> bool:
        """Execute a native mouse click at current or specified coordinates if enabled."""
        with self._lock:
            if not self._enabled:
                return False

        if x is not None and y is not None:
            self.move_cursor(x, y)

        btn = (button or "left").lower().strip()
        if btn == "right":
            down_flag = MOUSEEVENTF_RIGHTDOWN
            up_flag = MOUSEEVENTF_RIGHTUP
        elif btn == "middle":
            down_flag = MOUSEEVENTF_MIDDLEDOWN
            up_flag = MOUSEEVENTF_MIDDLEUP
        else:
            down_flag = MOUSEEVENTF_LEFTDOWN
            up_flag = MOUSEEVENTF_LEFTUP

        if sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.user32.mouse_event(down_flag, 0, 0, 0, 0)
                ctypes.windll.user32.mouse_event(up_flag, 0, 0, 0, 0)
                return True
            except Exception as exc:
                logger.error("Failed to execute mouse_event click (%s): %s", btn, exc)
                return False
        return True

    def double_click(
        self,
        x: float | int | None = None,
        y: float | int | None = None,
        button: str = "left",
    ) -> bool:
        """Execute a native double click at current or specified coordinates if enabled."""
        with self._lock:
            if not self._enabled:
                return False

        if x is not None and y is not None:
            self.move_cursor(x, y)

        c1 = self.click(x=None, y=None, button=button)
        if sys.platform == "win32":
            import time
            time.sleep(0.05)
        c2 = self.click(x=None, y=None, button=button)
        return c1 and c2

    def mouse_down(
        self,
        x: float | int | None = None,
        y: float | int | None = None,
        button: str = "left",
    ) -> bool:
        """Press and hold mouse button down at current or specified coordinates if enabled."""
        with self._lock:
            if not self._enabled:
                return False

        if x is not None and y is not None:
            self.move_cursor(x, y)

        btn = (button or "left").lower().strip()
        if btn == "right":
            down_flag = MOUSEEVENTF_RIGHTDOWN
        elif btn == "middle":
            down_flag = MOUSEEVENTF_MIDDLEDOWN
        else:
            down_flag = MOUSEEVENTF_LEFTDOWN

        if sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.user32.mouse_event(down_flag, 0, 0, 0, 0)
                return True
            except Exception as exc:
                logger.error("Failed to execute mouse_event mouse_down (%s): %s", btn, exc)
                return False
        return True

    def mouse_up(
        self,
        x: float | int | None = None,
        y: float | int | None = None,
        button: str = "left",
    ) -> bool:
        """Release mouse button at current or specified coordinates if enabled."""
        with self._lock:
            if not self._enabled:
                return False

        if x is not None and y is not None:
            self.move_cursor(x, y)

        btn = (button or "left").lower().strip()
        if btn == "right":
            up_flag = MOUSEEVENTF_RIGHTUP
        elif btn == "middle":
            up_flag = MOUSEEVENTF_MIDDLEUP
        else:
            up_flag = MOUSEEVENTF_LEFTUP

        if sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.user32.mouse_event(up_flag, 0, 0, 0, 0)
                return True
            except Exception as exc:
                logger.error("Failed to execute mouse_event mouse_up (%s): %s", btn, exc)
                return False
        return True

    def toggle(self, enable: bool | None = None) -> bool:
        """Toggle or explicitly set cursor takeover state."""
        with self._lock:
            if enable is None:
                self._enabled = not self._enabled
            else:
                self._enabled = bool(enable)
            state = self._enabled

        logger.info("SystemCursor toggle state: %s", state)
        return state

    def get_status(self) -> dict[str, Any]:
        """Return cursor controller operational status and screen resolution."""
        with self._lock:
            active = self._enabled

        width, height = self.screen_size
        return {
            "active": active,
            "enabled": active,
            "dpi_aware": self._dpi_aware,
            "screen_width": width,
            "screen_height": height,
        }


# Global singleton instance
system_cursor = SystemCursor(enabled=False)
