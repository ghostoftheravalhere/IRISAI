"""Safe desktop automation primitives used by voice commands."""

from __future__ import annotations

import csv
import io
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Literal

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Common voice target names → platform process identifiers.
_APP_PROCESS_MAP: dict[str, dict[str, str]] = {
    "chrome": {
        "win": "chrome.exe",
        "darwin": "Google Chrome",
        "linux": "chrome",
    },
    "notepad": {
        "win": "notepad.exe",
        "darwin": "TextEdit",
        "linux": "gedit",
    },
    "edge": {
        "win": "msedge.exe",
        "darwin": "Microsoft Edge",
        "linux": "microsoft-edge",
    },
}

_GRACEFUL_CLOSE_TIMEOUT_SECONDS = 2.0
_WM_CLOSE = 0x0010
_GW_OWNER = 4


CloseStatus = Literal["closed", "not_running", "failed", "unsupported"]


@dataclass(frozen=True)
class ApplicationCloseResult:
    """Outcome of a targeted application close attempt."""

    success: bool
    status: CloseStatus
    process_name: str | None = None


class DesktopController:
    """Small wrapper around OS and PyAutoGUI automation actions."""

    def __init__(self, screenshot_dir: str | Path | None = None) -> None:
        self._pyautogui: Any | None = None
        self._lock = RLock()
        self._screenshot_dir = Path(screenshot_dir) if screenshot_dir else Path.cwd() / "screenshots"

    def open_chrome(self) -> bool:
        """Launch Google Chrome using the platform launcher."""
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["cmd", "/c", "start", "", "chrome"])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "Google Chrome"])
            else:
                subprocess.Popen(["google-chrome"])
            logger.info("Voice automation launched Chrome.")
            return True
        except Exception:
            logger.exception("Failed to launch Chrome from voice command.")
            return False

    def open_notepad(self) -> bool:
        """Launch a simple text editor for the current platform."""
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["notepad.exe"])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "TextEdit"])
            else:
                subprocess.Popen(["gedit"])
            logger.info("Voice automation launched text editor.")
            return True
        except Exception:
            logger.exception("Failed to launch text editor from voice command.")
            return False

    def open_edge(self) -> bool:
        """Launch Microsoft Edge using the platform launcher."""
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["cmd", "/c", "start", "", "msedge"])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "Microsoft Edge"])
            else:
                subprocess.Popen(["microsoft-edge"])
            logger.info("Voice automation launched Edge.")
            return True
        except Exception:
            logger.exception("Failed to launch Edge from voice command.")
            return False

    def close_window(self) -> bool:
        """Close the currently focused window (Alt+F4)."""
        return self.hotkey("alt", "f4")

    def close_application(self, application_name: str) -> ApplicationCloseResult:
        """Close a named application with graceful close, then forced fallback.

        Windows flow:
        1. Locate the process and its top-level windows
        2. Post WM_CLOSE to each main window
        3. Wait up to 2 seconds for exit
        4. If still running, ``taskkill /F`` as fallback

        Does not use Alt+F4 — only the requested process is targeted.
        """
        process_name = self._resolve_process_name(application_name)
        if process_name is None:
            logger.warning("Unsupported close application target: %s", application_name)
            return ApplicationCloseResult(False, "unsupported")

        try:
            if not self.is_application_running(application_name):
                logger.info(
                    "Close skipped; application not running target=%s process=%s",
                    application_name,
                    process_name,
                )
                return ApplicationCloseResult(False, "not_running", process_name)

            if sys.platform.startswith("win"):
                closed = self._close_application_windows(process_name)
                if closed and self._wait_until_exited(process_name, _GRACEFUL_CLOSE_TIMEOUT_SECONDS):
                    logger.info(
                        "Voice automation gracefully closed application target=%s process=%s",
                        application_name,
                        process_name,
                    )
                    return ApplicationCloseResult(True, "closed", process_name)

                if self._force_kill_windows(process_name):
                    logger.info(
                        "Voice automation force-closed application target=%s process=%s",
                        application_name,
                        process_name,
                    )
                    return ApplicationCloseResult(True, "closed", process_name)

                logger.warning(
                    "Failed to close application %s (%s)",
                    application_name,
                    process_name,
                )
                return ApplicationCloseResult(False, "failed", process_name)

            if sys.platform == "darwin":
                subprocess.run(
                    ["osascript", "-e", f'quit app "{process_name}"'],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if self._wait_until_exited(process_name, _GRACEFUL_CLOSE_TIMEOUT_SECONDS):
                    return ApplicationCloseResult(True, "closed", process_name)
                subprocess.run(
                    ["pkill", "-f", process_name],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            else:
                subprocess.run(
                    ["pkill", "-f", process_name],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if not self._wait_until_exited(process_name, _GRACEFUL_CLOSE_TIMEOUT_SECONDS):
                    subprocess.run(
                        ["pkill", "-9", "-f", process_name],
                        capture_output=True,
                        text=True,
                        check=False,
                    )

            if self.is_application_running(application_name):
                return ApplicationCloseResult(False, "failed", process_name)

            logger.info(
                "Voice automation closed application target=%s process=%s",
                application_name,
                process_name,
            )
            return ApplicationCloseResult(True, "closed", process_name)
        except Exception:
            logger.exception(
                "Failed to close application target=%s process=%s",
                application_name,
                process_name,
            )
            return ApplicationCloseResult(False, "failed", process_name)

    def is_application_running(self, application_name: str) -> bool:
        """Return True when the mapped process appears to be running."""
        process_name = self._resolve_process_name(application_name)
        if process_name is None:
            return False
        return self._is_process_running(process_name)

    def _resolve_process_name(self, application_name: str) -> str | None:
        """Map a spoken application name to a platform process identifier."""
        key = (application_name or "").strip().lower()
        # Accept either friendly names or already-qualified executables.
        if key.endswith(".exe"):
            return key if sys.platform.startswith("win") else key[:-4]

        entry = _APP_PROCESS_MAP.get(key)
        if entry is None:
            return None

        if sys.platform.startswith("win"):
            return entry["win"]
        if sys.platform == "darwin":
            return entry["darwin"]
        return entry["linux"]

    def _is_process_running(self, process_name: str) -> bool:
        """Check whether a process with the given name is currently running."""
        if sys.platform.startswith("win"):
            return bool(self._list_windows_pids(process_name))

        try:
            completed = subprocess.run(
                ["pgrep", "-f", process_name],
                capture_output=True,
                text=True,
                check=False,
            )
            return completed.returncode == 0 and bool((completed.stdout or "").strip())
        except Exception:
            logger.exception("Failed to check process status for %s", process_name)
            return False

    def _list_windows_pids(self, process_name: str) -> list[int]:
        """Return PIDs for a Windows image name via tasklist CSV output."""
        try:
            completed = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            logger.exception("tasklist failed for %s", process_name)
            return []

        output = (completed.stdout or "").strip()
        if not output or "no tasks are running" in output.lower():
            return []

        pids: list[int] = []
        reader = csv.reader(io.StringIO(output))
        for row in reader:
            if len(row) < 2:
                continue
            image = row[0].strip().lower()
            if image != process_name.lower():
                continue
            try:
                pids.append(int(row[1].strip()))
            except ValueError:
                continue
        return pids

    def _close_application_windows(self, process_name: str) -> bool:
        """Post WM_CLOSE to top-level visible windows owned by the process."""
        pids = set(self._list_windows_pids(process_name))
        if not pids:
            return False

        try:
            import ctypes
            from ctypes import wintypes
        except Exception:
            logger.exception("ctypes unavailable for graceful window close.")
            return False

        user32 = ctypes.windll.user32
        hwnds: list[int] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _enum_proc(hwnd: int, _lparam: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            # Skip owned windows; close only top-level/main frames.
            if user32.GetWindow(hwnd, _GW_OWNER):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in pids:
                hwnds.append(int(hwnd))
            return True

        user32.EnumWindows(_enum_proc, 0)
        if not hwnds:
            logger.info("No visible main windows found for process %s", process_name)
            return False

        for hwnd in hwnds:
            user32.PostMessageW(hwnd, _WM_CLOSE, 0, 0)
        logger.info(
            "Posted WM_CLOSE to %d window(s) for process %s",
            len(hwnds),
            process_name,
        )
        return True

    def _wait_until_exited(self, process_name: str, timeout_seconds: float) -> bool:
        """Poll until the process exits or the timeout elapses."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if not self._is_process_running(process_name):
                return True
            time.sleep(0.1)
        return not self._is_process_running(process_name)

    def _force_kill_windows(self, process_name: str) -> bool:
        """Force-terminate a Windows process tree via taskkill."""
        completed = subprocess.run(
            ["taskkill", "/IM", process_name, "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0 and self._is_process_running(process_name):
            logger.warning(
                "taskkill fallback failed for %s: %s",
                process_name,
                (completed.stderr or completed.stdout or "").strip(),
            )
            return False
        return not self._is_process_running(process_name)

    def scroll(self, amount: int) -> bool:
        """Scroll the active window."""
        pyautogui = self._load_pyautogui()
        if pyautogui is None:
            return False

        try:
            pyautogui.scroll(amount)
            return True
        except Exception:
            logger.exception("Voice automation scroll failed.")
            return False

    def click(self, button: str = "left", clicks: int = 1) -> bool:
        """Click the mouse at the current cursor position."""
        pyautogui = self._load_pyautogui()
        if pyautogui is None:
            return False

        try:
            pyautogui.click(button=button, clicks=clicks)
            return True
        except Exception:
            logger.exception("Voice automation click failed.")
            return False

    def move_rel(self, x_offset: int, y_offset: int) -> bool:
        """Move the mouse relative to its current position."""
        pyautogui = self._load_pyautogui()
        if pyautogui is None:
            return False

        try:
            pyautogui.moveRel(x_offset, y_offset, duration=0)
            return True
        except Exception:
            logger.exception("Voice automation mouse move failed.")
            return False

    def press(self, key: str, presses: int = 1) -> bool:
        """Press a keyboard key."""
        pyautogui = self._load_pyautogui()
        if pyautogui is None:
            return False

        try:
            pyautogui.press(key, presses=presses)
            return True
        except Exception:
            logger.exception("Voice automation key press failed: %s", key)
            return False

    def hotkey(self, *keys: str) -> bool:
        """Press a keyboard shortcut."""
        pyautogui = self._load_pyautogui()
        if pyautogui is None:
            return False

        try:
            pyautogui.hotkey(*keys)
            return True
        except Exception:
            logger.exception("Voice automation hotkey failed: %s", "+".join(keys))
            return False

    def mute(self) -> bool:
        """Toggle system mute."""
        return self.press("volumemute")

    def take_screenshot(self) -> bool:
        """Capture a full-screen screenshot to the screenshots directory."""
        pyautogui = self._load_pyautogui()
        if pyautogui is None:
            return False

        try:
            self._screenshot_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self._screenshot_dir / f"iris_screenshot_{stamp}.png"
            image = pyautogui.screenshot()
            image.save(str(path))
            logger.info("Screenshot saved to %s", path)
            return True
        except Exception:
            logger.exception("Voice automation screenshot failed.")
            return False

    def _load_pyautogui(self) -> Any | None:
        """Load PyAutoGUI lazily so importing the backend has no desktop side effects."""
        with self._lock:
            if self._pyautogui is not None:
                return self._pyautogui

            try:
                import pyautogui
            except Exception:
                logger.exception("PyAutoGUI could not be loaded for voice automation.")
                return None

            pyautogui.FAILSAFE = True
            self._pyautogui = pyautogui
            return self._pyautogui
