"""OS and Window Navigation Dispatcher using Win32 API and hotkey injection."""

from __future__ import annotations

import sys
from backend.utils.logger import get_logger
from backend.voice.keyboard_injector import (
    send_hotkey,
    VK_CONTROL,
    VK_LWIN,
    VK_MENU,
    VK_TAB,
)

logger = get_logger(__name__)

try:
    import win32gui
    import win32con
    HAS_WIN32_GUI = True
except ImportError:
    win32gui = None  # type: ignore
    win32con = None  # type: ignore
    HAS_WIN32_GUI = False


class SystemNavigator:
    """
    Executes fast voice-driven OS window controls and app/browser navigation actions.
    """

    def dispatch(self, action: str) -> bool:
        """
        Dispatch navigation command.
        Prints unbuffered terminal output and performs Win32 window manipulation / hotkey injection.
        """
        if not action:
            return False

        act_clean = action.strip().lower()
        print(f">>> [VOICE NAV: {act_clean.upper()}] <<<", flush=True)

        if act_clean == "minimize":
            return self._minimize_window()
        elif act_clean == "maximize":
            return self._toggle_maximize_window()
        elif act_clean == "close window":
            return self._close_window()
        elif act_clean == "switch app":
            return send_hotkey(VK_MENU, VK_TAB)
        elif act_clean == "show desktop":
            return send_hotkey(VK_LWIN, 0x44)  # Win + D
        elif act_clean == "new tab":
            return send_hotkey(VK_CONTROL, 0x54)  # Ctrl + T
        elif act_clean == "close tab":
            return send_hotkey(VK_CONTROL, 0x57)  # Ctrl + W
        else:
            logger.warning("[SYSTEM NAVIGATOR] Unrecognized navigation action: %s", action)
            return False

    def _minimize_window(self) -> bool:
        if HAS_WIN32_GUI:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                return True
        logger.info("[MOCK NAV]: minimize foreground window")
        return True

    def _toggle_maximize_window(self) -> bool:
        if HAS_WIN32_GUI:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                if win32gui.IsZoomed(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                else:
                    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                return True
        logger.info("[MOCK NAV]: toggle maximize foreground window")
        return True

    def _close_window(self) -> bool:
        if HAS_WIN32_GUI:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                return True
        logger.info("[MOCK NAV]: close foreground window")
        return True
