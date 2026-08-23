"""
Centralized Windows Desktop Application Resolver & Launcher for IRIS AI.
Resolves natural-language application names to validated system executables,
Start Menu shortcuts (.lnk), or Windows App URI protocols without loose fallback.
"""

from __future__ import annotations

import os
import glob
import re
import sys
import subprocess
from dataclasses import dataclass
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ResolvedAppTarget:
    canonical_name: str
    app_key: str
    launch_type: str  # "exe", "shortcut", "uri", "system"
    target_path: str
    found: bool = True
    error_message: str | None = None


class DesktopAppResolver:
    """Centralized Windows Desktop Application Registry & Resolver."""

    _APP_REGISTRY: dict[str, dict] = {
        "word": {
            "name": "Microsoft Word",
            "aliases": ("microsoft word", "ms word", "word", "winword"),
            "exes": ("WINWORD.EXE", "winword.exe"),
            "shortcuts": ("*Word*.lnk", "*Microsoft Word*.lnk"),
            "uri": None,
        },
        "excel": {
            "name": "Microsoft Excel",
            "aliases": ("microsoft excel", "ms excel", "excel"),
            "exes": ("EXCEL.EXE", "excel.exe"),
            "shortcuts": ("*Excel*.lnk", "*Microsoft Excel*.lnk"),
            "uri": None,
        },
        "powerpoint": {
            "name": "Microsoft PowerPoint",
            "aliases": ("microsoft powerpoint", "ms powerpoint", "powerpoint", "ppt"),
            "exes": ("POWERPNT.EXE", "powerpnt.exe"),
            "shortcuts": ("*PowerPoint*.lnk", "*Microsoft PowerPoint*.lnk"),
            "uri": None,
        },
        "chrome": {
            "name": "Google Chrome",
            "aliases": ("google chrome", "chrome", "chrom", "browser"),
            "exes": ("chrome.exe",),
            "shortcuts": ("*Chrome*.lnk", "*Google Chrome*.lnk"),
            "uri": None,
        },
        "edge": {
            "name": "Microsoft Edge",
            "aliases": ("microsoft edge", "ms edge", "edge", "msedge"),
            "exes": ("msedge.exe",),
            "shortcuts": ("*Edge*.lnk", "*Microsoft Edge*.lnk"),
            "uri": None,
        },
        "firefox": {
            "name": "Mozilla Firefox",
            "aliases": ("mozilla firefox", "firefox"),
            "exes": ("firefox.exe",),
            "shortcuts": ("*Firefox*.lnk",),
            "uri": None,
        },
        "calculator": {
            "name": "Windows Calculator",
            "aliases": ("calculator", "calc", "windows calculator"),
            "exes": ("calc.exe",),
            "shortcuts": ("*Calculator*.lnk",),
            "uri": "calculator:",
        },
        "notepad": {
            "name": "Windows Notepad",
            "aliases": ("windows notepad", "notepad", "note pad", "editor"),
            "exes": ("notepad.exe",),
            "shortcuts": ("*Notepad*.lnk",),
            "uri": None,
        },
        "explorer": {
            "name": "File Explorer",
            "aliases": ("file explorer", "explorer", "windows explorer", "my computer", "files"),
            "exes": ("explorer.exe",),
            "shortcuts": ("*File Explorer*.lnk",),
            "uri": None,
        },
        "settings": {
            "name": "Windows Settings",
            "aliases": ("settings", "windows settings", "system settings", "setting", "control panel"),
            "exes": ("control.exe",),
            "shortcuts": ("*Settings*.lnk",),
            "uri": "ms-settings:",
        },
        "camera": {
            "name": "Windows Camera",
            "aliases": ("camera", "windows camera", "webcam app"),
            "exes": None,
            "shortcuts": ("*Camera*.lnk",),
            "uri": "microsoft.windows.camera:",
        },
        "vscode": {
            "name": "Visual Studio Code",
            "aliases": ("vscode", "vs code", "visual studio code", "code"),
            "exes": ("code.cmd", "code.exe"),
            "shortcuts": ("*Visual Studio Code*.lnk", "*Code*.lnk"),
            "uri": None,
        },
        "whatsapp": {
            "name": "WhatsApp",
            "aliases": ("whatsapp", "whats app"),
            "exes": ("WhatsApp.exe",),
            "shortcuts": ("*WhatsApp*.lnk",),
            "uri": "whatsapp:",
        },
        "spotify": {
            "name": "Spotify",
            "aliases": ("spotify", "music player"),
            "exes": ("Spotify.exe",),
            "shortcuts": ("*Spotify*.lnk",),
            "uri": "spotify:",
        },
        "taskmgr": {
            "name": "Task Manager",
            "aliases": ("task manager", "taskmgr", "task manager app"),
            "exes": ("taskmgr.exe",),
            "shortcuts": ("*Task Manager*.lnk",),
            "uri": None,
        },
        "cmd": {
            "name": "Command Prompt",
            "aliases": ("command prompt", "cmd", "terminal"),
            "exes": ("cmd.exe",),
            "shortcuts": ("*Command Prompt*.lnk",),
            "uri": None,
        },
    }

    def __init__(self) -> None:
        self._alias_map: dict[str, str] = {}
        for key, info in self._APP_REGISTRY.items():
            for alias in info["aliases"]:
                self._alias_map[alias.lower().strip()] = key

    def get_canonical_name(self, raw_name: str) -> str | None:
        """Return canonical display name for an application query if recognized."""
        key = self.resolve_app_key(raw_name)
        if key and key in self._APP_REGISTRY:
            return str(self._APP_REGISTRY[key]["name"])
        return None

    def resolve_app_key(self, raw_name: str) -> str | None:
        """Strictly map a requested application phrase to an app registry key."""
        if not raw_name:
            return None
        norm = raw_name.lower().strip()
        norm = re.sub(r"^(my|the|a|an)\s+", "", norm).strip()
        norm = re.sub(r"\s+(app|application|program|software)$", "", norm).strip()

        # 1. Exact alias match
        if norm in self._alias_map:
            return self._alias_map[norm]

        # 2. Strict token/word boundary match (never substring match!)
        for alias, key in self._alias_map.items():
            if re.search(rf"\b{re.escape(alias)}\b", norm) or norm == alias:
                return key

        return None

    def resolve_app_target(self, raw_name: str) -> ResolvedAppTarget:
        """Find executable, shortcut, or URI target for the requested application."""
        app_key = self.resolve_app_key(raw_name)
        if not app_key or app_key not in self._APP_REGISTRY:
            logger.warning("[APP RESOLUTION] Unrecognized application requested: '%s'", raw_name)
            return ResolvedAppTarget(
                canonical_name=raw_name,
                app_key="unknown",
                launch_type="none",
                target_path="",
                found=False,
                error_message=f"Application '{raw_name}' is not recognized.",
            )

        info = self._APP_REGISTRY[app_key]
        canonical_name = str(info["name"])

        # 0. Check URI Protocol for Windows System Apps (e.g. Settings, Camera)
        if app_key in ("settings", "camera") and info.get("uri"):
            uri = info["uri"]
            logger.info("[APP RESOLUTION] Resolved '%s' to Windows URI protocol: %s", raw_name, uri)
            return ResolvedAppTarget(
                canonical_name=canonical_name,
                app_key=app_key,
                launch_type="uri",
                target_path=uri,
                found=True,
            )

        # 1. Search Start Menu Shortcuts (.lnk)
        start_menu_dirs = [
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
        ]

        for pattern in info.get("shortcuts") or []:
            for sdir in start_menu_dirs:
                if not os.path.exists(sdir):
                    continue
                matches = glob.glob(os.path.join(sdir, "**", pattern), recursive=True)
                valid_matches = [m for m in matches if not any(bad in m.lower() for bad in ("cccp", "codec", "installer", "uninstall"))]
                if valid_matches:
                    shortcut_path = valid_matches[0]
                    logger.info("[APP RESOLUTION] Resolved '%s' to Start Menu shortcut: %s", raw_name, shortcut_path)
                    return ResolvedAppTarget(
                        canonical_name=canonical_name,
                        app_key=app_key,
                        launch_type="shortcut",
                        target_path=shortcut_path,
                        found=True,
                    )

        # 2. Search System PATH and Common Executable Directories
        for exe in info.get("exes") or []:
            # Check PATH via shutil.which
            import shutil
            found_exe = shutil.which(exe)
            if found_exe and os.path.exists(found_exe):
                logger.info("[APP RESOLUTION] Resolved '%s' to PATH executable: %s", raw_name, found_exe)
                return ResolvedAppTarget(
                    canonical_name=canonical_name,
                    app_key=app_key,
                    launch_type="exe",
                    target_path=found_exe,
                    found=True,
                )

            # Check standard Office / System installation paths
            search_paths = [
                os.path.expandvars(r"%ProgramFiles%\Microsoft Office\root\Office16"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft Office\root\Office16"),
                os.path.expandvars(r"%ProgramFiles%\Microsoft Office\Office16"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft Office\Office16"),
                os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application"),
                os.path.expandvars(r"%SystemRoot%\System32"),
                os.path.expandvars(r"%SystemRoot%"),
            ]
            for spath in search_paths:
                candidate = os.path.join(spath, exe)
                if os.path.exists(candidate):
                    logger.info("[APP RESOLUTION] Resolved '%s' to system path: %s", raw_name, candidate)
                    return ResolvedAppTarget(
                        canonical_name=canonical_name,
                        app_key=app_key,
                        launch_type="exe",
                        target_path=candidate,
                        found=True,
                    )

        # 3. URI Fallback (e.g. ms-settings:, calculator:, microsoft.windows.camera:)
        uri = info.get("uri")
        if uri:
            logger.info("[APP RESOLUTION] Resolved '%s' to Windows URI protocol: %s", raw_name, uri)
            return ResolvedAppTarget(
                canonical_name=canonical_name,
                app_key=app_key,
                launch_type="uri",
                target_path=uri,
                found=True,
            )

        logger.warning("[APP RESOLUTION] Application '%s' (key: %s) is not installed on this system.", raw_name, app_key)
        return ResolvedAppTarget(
            canonical_name=canonical_name,
            app_key=app_key,
            launch_type="none",
            target_path="",
            found=False,
            error_message=f"Application '{canonical_name}' is not installed on this computer.",
        )

    def launch(self, target: ResolvedAppTarget) -> tuple[bool, str]:
        """Safely launch a resolved application target."""
        if not target.found or not target.target_path:
            msg = target.error_message or f"Sir, I couldn't find {target.canonical_name} on this computer."
            logger.warning("[APP LAUNCH FAILED] Requested: '%s' Reason: %s", target.canonical_name, msg)
            return False, msg

        try:
            if target.launch_type == "shortcut":
                if sys.platform.startswith("win"):
                    os.startfile(target.target_path)
                else:
                    subprocess.Popen(["open", target.target_path])
            elif target.launch_type == "exe":
                subprocess.Popen([target.target_path])
            elif target.launch_type == "uri":
                if sys.platform.startswith("win"):
                    subprocess.Popen(["cmd", "/c", "start", "", target.target_path])
                else:
                    subprocess.Popen(["open", target.target_path])
            else:
                subprocess.Popen([target.target_path])

            success_msg = f"{target.canonical_name} opened."
            logger.info(
                "[APP LAUNCH SUCCESS] Requested: '%s' Resolved: '%s' Target: '%path' Method: %s",
                target.canonical_name,
                target.canonical_name,
                target.target_path,
                target.launch_type,
            )
            return True, success_msg
        except Exception as exc:
            err_msg = f"Failed to launch {target.canonical_name}: {exc}"
            logger.exception("[APP LAUNCH ERROR] %s", err_msg)
            return False, err_msg


# Singleton Instance
app_resolver = DesktopAppResolver()
