"""Multimodal Action Dispatcher for low-latency Win32 mouse click and scroll execution."""

from __future__ import annotations

import sys
import time
from threading import Event, Lock, Thread
from typing import Any

from backend.utils.logger import get_logger

logger = get_logger(__name__)

from backend.voice.system_navigator import SystemNavigator
from backend.voice.dictation_engine import WhisperDictationEngine
from backend.voice.keyboard_injector import type_unicode_text

try:
    import win32api
    import win32con
    HAS_WIN32 = True
except ImportError:
    win32api = None  # type: ignore
    win32con = None  # type: ignore
    HAS_WIN32 = False


class MultimodalActionDispatcher:
    """
    Executes gaze-directed mouse actions (click, double click, right click, hold/drag, release, scroll),
    dictation/typing, and OS/Window navigation commands directly via Win32 APIs.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._scroll_stop_event = Event()
        self._scroll_thread: Thread | None = None
        self._scroll_delta: int = 0
        self._is_holding: bool = False
        self._navigator = SystemNavigator()
        self._dictation_engine = WhisperDictationEngine()
        self._dictation_active: bool = False
        self._single_type_pending: bool = False

    @property
    def dictation_active(self) -> bool:
        return self._dictation_active

    @dictation_active.setter
    def dictation_active(self, value: bool) -> None:
        self._dictation_active = bool(value)

    def type_text(self, text: str) -> bool:
        """Inject unicode text directly into the focused window."""
        if not text:
            return False
        print(f">>> [VOICE TYPE: '{text}'] <<<", flush=True)
        return type_unicode_text(text)

    def dispatch(self, command: str) -> bool:
        """
        Dispatch action corresponding to the recognized voice command.
        Prints unbuffered terminal output and performs Win32 injection / navigation.
        """
        if not command:
            return False

        cmd_clean = command.strip().lower()
        print(f">>> [VOICE ACTION: {cmd_clean.upper()}] <<<", flush=True)

        # Mouse Actions
        if cmd_clean in ("click", "tap"):
            self._left_click()
            return True
        elif cmd_clean == "right click":
            self._right_click()
            return True
        elif cmd_clean == "double click":
            self._double_click()
            return True
        elif cmd_clean in ("hold", "drag"):
            self._left_down()
            return True
        elif cmd_clean in ("release", "drop"):
            self._left_up()
            return True
        elif cmd_clean == "scroll up":
            self.start_scroll(direction=1)
            return True
        elif cmd_clean == "scroll down":
            self.start_scroll(direction=-1)
            return True
        elif cmd_clean == "stop":
            self.stop_scroll()
            self._dictation_active = False
            return True
        # Dictation Toggles
        elif cmd_clean == "start dictation":
            self._dictation_active = True
            print(">>> [DICTATION MODE: ACTIVE] <<<", flush=True)
            return True
        elif cmd_clean == "stop dictation":
            self._dictation_active = False
            print(">>> [DICTATION MODE: STOPPED] <<<", flush=True)
            return True
        elif cmd_clean == "type":
            # Focus current gaze target with left click
            self._left_click()
            self._single_type_pending = True
            print(">>> [LOOK & TYPE: TARGET FOCUSED] <<<", flush=True)
            return True
        # OS Navigation Commands
        elif cmd_clean in ("minimize", "maximize", "close window", "switch app", "show desktop", "new tab", "close tab"):
            return self._navigator.dispatch(cmd_clean)
        else:
            logger.warning("[ACTION ENGINE] Unrecognized action command: %s", command)
            return False

    def _left_click(self) -> None:
        if HAS_WIN32:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.010)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        self._is_holding = False

    def _right_click(self) -> None:
        if HAS_WIN32:
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            time.sleep(0.010)
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)

    def _double_click(self) -> None:
        if HAS_WIN32:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.060)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        self._is_holding = False

    def _left_down(self) -> None:
        if HAS_WIN32:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        self._is_holding = True

    def _left_up(self) -> None:
        if HAS_WIN32:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        self._is_holding = False

    def start_scroll(self, direction: int = 1) -> None:
        """
        Start continuous background scroll daemon thread.
        direction > 0 for scroll up (+120), direction < 0 for scroll down (-120).
        """
        with self._lock:
            self.stop_scroll()
            self._scroll_delta = 120 if direction > 0 else -120
            self._scroll_stop_event.clear()
            self._scroll_thread = Thread(target=self._scroll_loop, name="continuous-scroll", daemon=True)
            self._scroll_thread.start()

    def stop_scroll(self) -> None:
        """Signal and stop continuous scroll daemon thread."""
        thread = self._scroll_thread
        self._scroll_stop_event.set()
        if thread is not None and thread.is_alive():
            thread.join(timeout=0.5)
        self._scroll_thread = None

    def _scroll_loop(self) -> None:
        """Daemon thread emitting MOUSEEVENTF_WHEEL every 80ms until stopped."""
        while not self._scroll_stop_event.is_set():
            if HAS_WIN32:
                win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, self._scroll_delta, 0)
            time.sleep(0.080)
