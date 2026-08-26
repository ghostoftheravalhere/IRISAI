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
    "google chrome": {
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
    "microsoft edge": {
        "win": "msedge.exe",
        "darwin": "Microsoft Edge",
        "linux": "microsoft-edge",
    },
    "microsoft word": {
        "win": "winword.exe",
        "darwin": "Microsoft Word",
        "linux": "word",
    },
    "word": {
        "win": "winword.exe",
        "darwin": "Microsoft Word",
        "linux": "word",
    },
    "winword": {
        "win": "winword.exe",
        "darwin": "Microsoft Word",
        "linux": "word",
    },
    "microsoft powerpoint": {
        "win": "powerpnt.exe",
        "darwin": "Microsoft PowerPoint",
        "linux": "powerpoint",
    },
    "power point": {
        "win": "powerpnt.exe",
        "darwin": "Microsoft PowerPoint",
        "linux": "powerpoint",
    },
    "powerpoint": {
        "win": "powerpnt.exe",
        "darwin": "Microsoft PowerPoint",
        "linux": "powerpoint",
    },
    "ppt": {
        "win": "powerpnt.exe",
        "darwin": "Microsoft PowerPoint",
        "linux": "powerpoint",
    },
    "microsoft excel": {
        "win": "excel.exe",
        "darwin": "Microsoft Excel",
        "linux": "excel",
    },
    "excel": {
        "win": "excel.exe",
        "darwin": "Microsoft Excel",
        "linux": "excel",
    },
    "file explorer": {
        "win": "explorer.exe",
        "darwin": "Finder",
        "linux": "nautilus",
    },
    "explorer": {
        "win": "explorer.exe",
        "darwin": "Finder",
        "linux": "nautilus",
    },
    "files": {
        "win": "explorer.exe",
        "darwin": "Finder",
        "linux": "nautilus",
    },
    "this pc": {
        "win": "explorer.exe",
        "darwin": "Finder",
        "linux": "nautilus",
    },
    "my computer": {
        "win": "explorer.exe",
        "darwin": "Finder",
        "linux": "nautilus",
    },
    "windows explorer": {
        "win": "explorer.exe",
        "darwin": "Finder",
        "linux": "nautilus",
    },
    "calculator": {
        "win": "calc.exe",
        "darwin": "Calculator",
        "linux": "gnome-calculator",
    },
    "calc": {
        "win": "calc.exe",
        "darwin": "Calculator",
        "linux": "gnome-calculator",
    },
    "teams": {
        "win": "ms-teams.exe",
        "darwin": "Microsoft Teams",
        "linux": "teams",
    },
    "microsoft teams": {
        "win": "ms-teams.exe",
        "darwin": "Microsoft Teams",
        "linux": "teams",
    },
    "spotify": {
        "win": "Spotify.exe",
        "darwin": "Spotify",
        "linux": "spotify",
    },
    "discord": {
        "win": "Discord.exe",
        "darwin": "Discord",
        "linux": "discord",
    },
    "settings": {
        "win": "SystemSettings.exe",
        "darwin": "System Settings",
        "linux": "gnome-control-center",
    },
    "camera": {
        "win": "WindowsCamera.exe",
        "darwin": "Camera",
        "linux": "cheese",
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

    def open_settings(self) -> bool:
        """Launch Windows Settings app."""
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["cmd", "/c", "start", "ms-settings:"])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "System Settings"])
            else:
                subprocess.Popen(["gnome-control-center"])
            logger.info("Voice automation launched Settings.")
            return True
        except Exception:
            logger.exception("Failed to launch Settings from voice command.")
            return False

    def open_camera(self) -> bool:
        """Launch Windows Camera application via ms-camera URI protocol."""
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["cmd", "/c", "start", "microsoft.windows.camera:"])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "Photo Booth"])
            else:
                subprocess.Popen(["cheese"])
            logger.info("Voice automation launched Camera application.")
            return True
        except Exception:
            logger.exception("Failed to launch Camera application from voice command.")
            return False

    _SUPPORTED_APPS: dict[str, tuple[str, ...]] = {
        "chrome": ("chrome", "google chrome", "chrom", "browser"),
        "notepad": ("notepad", "note pad", "editor"),
        "edge": ("edge", "microsoft edge", "ms edge", "msedge"),
        "settings": ("settings", "setting", "windows settings", "system settings", "control panel"),
        "camera": ("camera", "windows camera", "webcam app", "photo booth"),
        "vscode": ("vscode", "vs code", "visual studio code", "code"),
        "whatsapp": ("whatsapp", "whats app"),
        "spotify": ("spotify", "music player"),
        "calculator": ("calculator", "calc"),
        "explorer": ("explorer", "file explorer", "files", "my computer"),
        "taskmgr": ("taskmgr", "task manager"),
        "cmd": ("cmd", "command prompt", "terminal"),
    }

    def is_application_supported(self, application_name: str) -> bool:
        """Validate whether an application target phrase matches a supported system app mapping."""
        from backend.automation.app_resolver import app_resolver
        return app_resolver.resolve_app_key(application_name) is not None

    def open_application(self, application_name: str) -> bool:
        """Open an application by name via DesktopAppResolver cleanly and safely."""
        app = (application_name or "").strip()
        if not app:
            logger.warning("open_application rejected: Empty application name.")
            return False

        if app.startswith(("http://", "https://")):
            try:
                import webbrowser
                webbrowser.open(app)
                return True
            except Exception:
                return False

        from backend.automation.app_resolver import app_resolver
        target = app_resolver.resolve_app_target(app)
        if not target.found:
            logger.warning("[APP LAUNCH] Application '%s' not found on system: %s", app, target.error_message)
            return False

        success, msg = app_resolver.launch(target)
        return success

    def close_window(self) -> bool:
        """Close the currently focused window (Alt+F4)."""
        return self.hotkey("alt", "f4")

    def is_application_running(self, application_name: str) -> bool:
        """Return True when the application or process is currently running."""
        app = (application_name or "").strip()
        if not app:
            return False

        # File Explorer check (active folder windows rather than shell process)
        is_explorer = app.lower() in ("explorer", "file explorer", "files", "this pc", "my computer", "windows explorer")
        if is_explorer and sys.platform.startswith("win"):
            from backend.automation.app_resolver import app_resolver
            resolved = app_resolver.resolve_running_app(app)
            return bool(resolved.matched and (resolved.pids or resolved.window_handles))

        # Fast path via centralized process map (excluding explorer.exe which is permanent desktop shell)
        process_name = self._resolve_process_name(app)
        if process_name and process_name.lower() != "explorer.exe" and self._is_process_running(process_name):
            return True

        from backend.automation.app_resolver import app_resolver
        resolved = app_resolver.resolve_running_app(app)
        return bool(resolved.matched and (resolved.pids or resolved.window_handles))

    def close_application(self, application_name: str) -> ApplicationCloseResult:
        """Close a named application with graceful close, then forced fallback.

        Windows flow:
        1. Resolve target application PIDs and executable metadata dynamically via app_resolver
        2. For File Explorer, close folder windows via WM_CLOSE without terminating explorer.exe
        3. For standard apps, post WM_CLOSE to main windows of target PIDs
        4. Wait up to 2 seconds for exit; force-terminate only target PIDs if not exited
        """
        app = (application_name or "").strip()
        if not app:
            return ApplicationCloseResult(False, "unsupported")

        from backend.automation.app_resolver import app_resolver
        resolved_running = app_resolver.resolve_running_app(app)
        resolved_installed = app_resolver.resolve_app_target(app)
        canonical_name = resolved_running.name or (resolved_installed.canonical_name if resolved_installed and resolved_installed.found else app.title())

        process_name = self._resolve_process_name(app)

        # Special safety path for File Explorer (CabinetWClass)
        is_explorer = (
            app.lower() in ("explorer", "file explorer", "files", "this pc", "my computer", "windows explorer")
            or (process_name and process_name.lower() == "explorer.exe")
            or canonical_name.lower() in ("file explorer", "windows explorer")
        )
        if is_explorer and sys.platform.startswith("win"):
            closed = self._close_explorer_windows()
            if closed:
                logger.info("Voice automation closed File Explorer window(s)")
                return ApplicationCloseResult(True, "closed", "File Explorer")
            else:
                logger.info("No open File Explorer windows found to close")
                return ApplicationCloseResult(False, "not_running", "File Explorer")

        pids = list(resolved_running.pids)
        if not pids and process_name:
            pids = self._list_windows_pids(process_name)

        if not pids and not self.is_application_running(app):
            logger.info("Close skipped; application not running target=%s", app)
            return ApplicationCloseResult(False, "not_running", canonical_name)

        logger.info(
            "Targeting application '%s' for closure: pids=%s procs=%s source=%s",
            canonical_name,
            pids,
            resolved_running.process_names,
            resolved_running.source,
        )

        try:
            if sys.platform.startswith("win"):
                # 1. Post WM_CLOSE to main windows of target PIDs
                if pids:
                    self._close_windows_by_pids(pids)
                elif process_name:
                    self._close_application_windows(process_name)

                # Wait for target PIDs or process_name to exit
                if pids and self._wait_until_pids_exited(pids, _GRACEFUL_CLOSE_TIMEOUT_SECONDS):
                    # Clean up any lingering background child processes if needed
                    if process_name and self._is_process_running(process_name):
                        self._force_kill_windows(process_name)
                    logger.info("Voice automation gracefully closed application '%s' (pids=%s)", canonical_name, pids)
                    return ApplicationCloseResult(True, "closed", canonical_name)
                elif process_name and self._wait_until_exited(process_name, _GRACEFUL_CLOSE_TIMEOUT_SECONDS):
                    logger.info("Voice automation gracefully closed application '%s'", canonical_name)
                    return ApplicationCloseResult(True, "closed", canonical_name)

                # 2. Force termination fallback
                if pids:
                    if self._force_kill_pids(pids):
                        logger.info("Voice automation force-closed application '%s' (pids=%s)", canonical_name, pids)
                        return ApplicationCloseResult(True, "closed", canonical_name)
                elif process_name:
                    if self._force_kill_windows(process_name):
                        return ApplicationCloseResult(True, "closed", canonical_name)

                # Final verification
                if (pids and self._wait_until_pids_exited(pids, 0.5)) or (process_name and self._wait_until_exited(process_name, 0.5)):
                    return ApplicationCloseResult(True, "closed", canonical_name)

                logger.warning("Failed to close application '%s' (pids=%s)", canonical_name, pids)
                return ApplicationCloseResult(False, "failed", canonical_name)

            if sys.platform == "darwin":
                pname = process_name or app
                for p in ([pname] + resolved_running.process_names):
                    subprocess.run(["osascript", "-e", f'quit app "{p}"'], capture_output=True, text=True, check=False)
                if (pids and self._wait_until_pids_exited(pids, _GRACEFUL_CLOSE_TIMEOUT_SECONDS)) or self._wait_until_exited(pname, _GRACEFUL_CLOSE_TIMEOUT_SECONDS):
                    return ApplicationCloseResult(True, "closed", canonical_name)
                for pid in pids:
                    subprocess.run(["kill", "-9", str(pid)], capture_output=True, text=True, check=False)
            else:
                pname = process_name or app
                for pid in pids:
                    subprocess.run(["kill", "-15", str(pid)], capture_output=True, text=True, check=False)
                if not ((pids and self._wait_until_pids_exited(pids, _GRACEFUL_CLOSE_TIMEOUT_SECONDS)) or self._wait_until_exited(pname, _GRACEFUL_CLOSE_TIMEOUT_SECONDS)):
                    for pid in pids:
                        subprocess.run(["kill", "-9", str(pid)], capture_output=True, text=True, check=False)

            if self.is_application_running(app):
                return ApplicationCloseResult(False, "failed", canonical_name)

            return ApplicationCloseResult(True, "closed", canonical_name)
        except Exception:
            logger.exception("Failed to close application target=%s", app)
            return ApplicationCloseResult(False, "failed", canonical_name)

    def _resolve_process_name(self, application_name: str) -> str | None:
        """Map a spoken application name to a platform process identifier."""
        key = (application_name or "").strip().lower()
        if key.endswith(".exe"):
            return key if sys.platform.startswith("win") else key[:-4]

        entry = _APP_PROCESS_MAP.get(key)
        if entry is not None:
            if sys.platform.startswith("win"):
                return entry["win"]
            if sys.platform == "darwin":
                return entry["darwin"]
            return entry["linux"]

        return None

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
        """Return PIDs for a Windows image name via psutil or tasklist."""
        try:
            import psutil
            pids = []
            for p in psutil.process_iter(["pid", "name"]):
                try:
                    if (p.info["name"] or "").lower() == process_name.lower():
                        pids.append(p.info["pid"])
                except Exception:
                    pass
            if pids:
                return pids
        except ImportError:
            pass

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

    def _close_windows_by_pids(self, pids: list[int]) -> bool:
        """Post WM_CLOSE to top-level visible windows owned by the specific PIDs."""
        pid_set = set(pids)
        if not pid_set:
            return False

        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
        except Exception:
            logger.exception("ctypes unavailable for graceful window close.")
            return False

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
            if pid.value in pid_set:
                hwnds.append(int(hwnd))
            return True

        user32.EnumWindows(_enum_proc, 0)
        for hwnd in hwnds:
            user32.PostMessageW(hwnd, _WM_CLOSE, 0, 0)
        logger.info("Posted WM_CLOSE to %d window(s) for PIDs %s", len(hwnds), pids)
        return bool(hwnds)

    def _close_explorer_windows(self) -> bool:
        """Post WM_CLOSE strictly to visible File Explorer folder windows (CabinetWClass), never shell/taskbar."""
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
        except Exception:
            return False

        hwnds: list[int] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _enum_proc(hwnd: int, _lparam: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            if user32.GetWindow(hwnd, _GW_OWNER):
                return True
            class_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buf, 256)
            class_name = class_buf.value.strip()
            if class_name in ("CabinetWClass", "ExploreWClass"):
                hwnds.append(int(hwnd))
            return True

        user32.EnumWindows(_enum_proc, 0)
        for hwnd in hwnds:
            user32.PostMessageW(hwnd, _WM_CLOSE, 0, 0)
        logger.info("Posted WM_CLOSE to %d File Explorer folder window(s)", len(hwnds))
        return bool(hwnds)

    def _close_application_windows(self, process_name: str) -> bool:
        """Post WM_CLOSE to top-level visible windows owned by the process name."""
        pids = self._list_windows_pids(process_name)
        return self._close_windows_by_pids(pids)

    def _wait_until_pids_exited(self, pids: list[int], timeout_seconds: float) -> bool:
        """Poll until target PIDs have terminated or timeout expires."""
        try:
            import psutil
        except ImportError:
            return True

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            remaining = [pid for pid in pids if psutil.pid_exists(pid)]
            if not remaining:
                return True
            time.sleep(0.1)
        remaining = [pid for pid in pids if psutil.pid_exists(pid)]
        return len(remaining) == 0

    def _wait_until_exited(self, process_name: str, timeout_seconds: float) -> bool:
        """Poll until the process exits or the timeout elapses."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if not self._is_process_running(process_name):
                return True
            time.sleep(0.1)
        return not self._is_process_running(process_name)

    def _force_kill_pids(self, pids: list[int]) -> bool:
        """Force-terminate target PIDs safely."""
        try:
            import psutil
            for pid in pids:
                if psutil.pid_exists(pid):
                    try:
                        p = psutil.Process(pid)
                        for child in p.children(recursive=True):
                            try:
                                child.kill()
                            except Exception:
                                pass
                        p.kill()
                    except Exception:
                        pass
            if self._wait_until_pids_exited(pids, 1.0):
                return True
        except Exception:
            pass

        if sys.platform.startswith("win"):
            for pid in pids:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, text=True, check=False)
            return self._wait_until_pids_exited(pids, 1.0)
        return False

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
            self._ensure_safe_cursor_position(pyautogui)
            old_failsafe = pyautogui.FAILSAFE
            try:
                pyautogui.FAILSAFE = False
                pyautogui.click(button=button, clicks=clicks)
            finally:
                pyautogui.FAILSAFE = old_failsafe
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
            self._ensure_safe_cursor_position(pyautogui)
            old_failsafe = pyautogui.FAILSAFE
            try:
                pyautogui.FAILSAFE = False
                pyautogui.press(key, presses=presses)
            finally:
                pyautogui.FAILSAFE = old_failsafe
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
            self._ensure_safe_cursor_position(pyautogui)
            old_failsafe = pyautogui.FAILSAFE
            try:
                pyautogui.FAILSAFE = False
                pyautogui.hotkey(*keys)
            finally:
                pyautogui.FAILSAFE = old_failsafe
            return True
        except Exception:
            logger.exception("Voice automation hotkey failed: %s", "+".join(keys))
            return False

    def _ensure_safe_cursor_position(self, pyautogui) -> None:
        """Ensure mouse cursor is positioned away from screen corners to prevent PyAutoGUI fail-safe triggers."""
        try:
            cur_x, cur_y = pyautogui.position()
            screen_w, screen_h = pyautogui.size()
            if cur_x <= 10 or cur_y <= 10 or cur_x >= screen_w - 10 or cur_y >= screen_h - 10:
                old_failsafe = pyautogui.FAILSAFE
                try:
                    pyautogui.FAILSAFE = False
                    safe_x, safe_y = max(100, screen_w // 2), max(100, screen_h // 2)
                    pyautogui.moveTo(safe_x, safe_y)
                finally:
                    pyautogui.FAILSAFE = old_failsafe
        except Exception:
            pass

    def type_text(self, text: str) -> bool:
        """Type a text string into the currently focused window."""
        pyautogui = self._load_pyautogui()
        if pyautogui is None:
            return False

        try:
            self._ensure_safe_cursor_position(pyautogui)
            old_failsafe = pyautogui.FAILSAFE
            try:
                pyautogui.FAILSAFE = False
                pyautogui.write(text, interval=0.01)
            finally:
                pyautogui.FAILSAFE = old_failsafe
            return True
        except Exception:
            logger.exception("Voice automation type_text failed: %s", text)
            return False

    def wait_for_condition(
        self,
        condition_func: Callable[[], bool],
        timeout_sec: float = 5.0,
        poll_interval_sec: float = 0.05,
        description: str = "condition",
    ) -> bool:
        """Poll until condition_func returns True or timeout_sec elapses."""
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            if condition_func():
                return True
            time.sleep(poll_interval_sec)
        result = condition_func()
        if not result:
            logger.warning("Timed out waiting for %s after %.2fs", description, timeout_sec)
        return result

    def wait_for_window(self, application_name: str, timeout_sec: float = 3.0) -> bool:
        """Wait until a visible window matching application_name exists."""
        process_name = self._resolve_process_name(application_name)
        if process_name is None:
            return True

        return self.wait_for_condition(
            lambda: self._find_window_hwnd(process_name) is not None,
            timeout_sec=timeout_sec,
            poll_interval_sec=0.05,
            description=f"window '{application_name}'",
        )

    def wait_for_window_active(self, application_name: str, timeout_sec: float = 3.0) -> bool:
        """Wait until application_name is restored and active in the foreground."""
        process_name = self._resolve_process_name(application_name)
        if process_name is None:
            return True

        def _check_and_activate() -> bool:
            if self.is_window_active(application_name):
                return True
            self.activate_window(application_name)
            return self.is_window_active(application_name)

        return self.wait_for_condition(
            _check_and_activate,
            timeout_sec=timeout_sec,
            poll_interval_sec=0.05,
            description=f"foreground focus for '{application_name}'",
        )

    def activate_window(self, application_name: str) -> bool:
        """Restore and bring the main window of application_name to foreground."""
        process_name = self._resolve_process_name(application_name)
        if process_name is None:
            return True

        hwnd = self._find_window_hwnd(process_name)
        if hwnd is None:
            logger.warning("Cannot activate window; no HWND found for %s", process_name)
            return False

        if sys.platform.startswith("win"):
            try:
                import ctypes

                user32 = ctypes.windll.user32
                # SW_RESTORE = 9
                user32.ShowWindow(hwnd, 9)
                user32.SetForegroundWindow(hwnd)
                user32.BringWindowToTop(hwnd)
                logger.info("Activated window HWND %s for process %s", hwnd, process_name)
                return True
            except Exception:
                logger.exception("Failed to activate window HWND %s", hwnd)
                return False

        return True

    def is_window_active(self, application_name: str) -> bool:
        """Return True if the current foreground window belongs to application_name."""
        process_name = self._resolve_process_name(application_name)
        if process_name is None:
            return True

        if sys.platform.startswith("win"):
            try:
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.windll.user32
                foreground_hwnd = user32.GetForegroundWindow()
                if not foreground_hwnd:
                    return False

                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(foreground_hwnd, ctypes.byref(pid))
                pids = set(self._list_windows_pids(process_name))
                is_active = pid.value in pids
                logger.info("Active window verification for '%s': active=%s", application_name, is_active)
                return is_active
            except Exception:
                logger.exception("Failed to check active window status for %s", process_name)
                return False

        return True

    def _find_window_hwnd(self, process_name: str) -> int | None:
        """Find the HWND of the main visible window owned by process_name."""
        pids = set(self._list_windows_pids(process_name))
        if not pids:
            return None

        if not sys.platform.startswith("win"):
            return 1  # Dummy HWND for non-Windows platforms

        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            found_hwnd: list[int] = []

            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def _enum_proc(hwnd: int, _lparam: int) -> bool:
                if not user32.IsWindowVisible(hwnd):
                    return True
                if user32.GetWindow(hwnd, _GW_OWNER):
                    return True
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value in pids:
                    found_hwnd.append(int(hwnd))
                    return False
                return True

            user32.EnumWindows(_enum_proc, 0)
            return found_hwnd[0] if found_hwnd else None
        except Exception:
            return None

    def browser_search(self, application: str, query: str) -> bool:
        """Open browser application, focus address bar, type search query, and press Enter."""
        app_name = (application or "chrome").strip().lower()
        logger.info("Executing browser search in '%s' for query: '%s'", app_name, query)
        self.open_application(app_name)

        if not self.wait_for_window(app_name, timeout_sec=3.0):
            logger.warning("browser_search timed out waiting for window '%s'", app_name)
            return False

        if not self.wait_for_window_active(app_name, timeout_sec=3.0):
            logger.warning("browser_search failed foreground focus verification for '%s'", app_name)

        self.hotkey("ctrl", "l")
        self.type_text(query)
        return self.press("enter")

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
