"""
Centralized Generalized Windows Desktop Application Resolver & Launcher for IRIS AI.
Dynamically discovers and resolves Win32, UWP/MSIX, Start Menu, Registry App Paths,
Uninstall Registry, and URI protocol applications for hands-free Windows automation.
"""

from __future__ import annotations

import os
import glob
import re
import sys
import shutil
import winreg
import subprocess
from dataclasses import dataclass
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ResolvedAppTarget:
    canonical_name: str
    app_key: str
    launch_type: str  # "exe", "shortcut", "uri", "shell", "system"
    target_path: str
    found: bool = True
    error_message: str | None = None
    source: str = "Unknown"


class DesktopAppResolver:
    """Generalized Multi-Tier Windows Desktop Application Registry & Resolver."""

    _APP_REGISTRY: dict[str, dict] = {
        "word": {
            "name": "Microsoft Word",
            "aliases": ("microsoft word", "ms word", "word", "winword", "doc", "docs"),
            "exes": ("WINWORD.EXE", "winword.exe"),
            "shortcuts": ("*Word*.lnk", "*Microsoft Word*.lnk"),
            "uri": "ms-word:",
        },
        "excel": {
            "name": "Microsoft Excel",
            "aliases": ("microsoft excel", "ms excel", "excel", "spreadsheet", "sheets"),
            "exes": ("EXCEL.EXE", "excel.exe"),
            "shortcuts": ("*Excel*.lnk", "*Microsoft Excel*.lnk"),
            "uri": "ms-excel:",
        },
        "powerpoint": {
            "name": "Microsoft PowerPoint",
            "aliases": ("microsoft powerpoint", "ms powerpoint", "powerpoint", "ppt", "presentation", "slides"),
            "exes": ("POWERPNT.EXE", "powerpnt.exe"),
            "shortcuts": ("*PowerPoint*.lnk", "*Microsoft PowerPoint*.lnk"),
            "uri": "ms-powerpoint:",
        },
        "teams": {
            "name": "Microsoft Teams",
            "aliases": ("microsoft teams", "ms teams", "teams", "msteams", "teams meeting"),
            "exes": ("ms-teams.exe", "Teams.exe"),
            "shortcuts": ("*Teams*.lnk", "*Microsoft Teams*.lnk"),
            "uri": "msteams:",
        },
        "zoom": {
            "name": "Zoom Workplace",
            "aliases": ("zoom workplace", "zoom", "zoom meeting", "zoom app"),
            "exes": ("Zoom.exe",),
            "shortcuts": ("*Zoom*.lnk", "*Zoom Workplace*.lnk"),
            "uri": "zoommtg:",
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
            "exes": ("calc.exe", "CalculatorApp.exe"),
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
            "aliases": ("camera", "windows camera", "webcam app", "webcam"),
            "exes": ("WindowsCamera.exe",),
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

    def get_canonical_name(self, raw_name: str) -> str:
        """Return canonical display name for an application query."""
        key = self.resolve_app_key(raw_name)
        if key and key in self._APP_REGISTRY:
            return str(self._APP_REGISTRY[key]["name"])
        # If not in static registry, format raw name
        clean = raw_name.strip()
        return clean.title() if clean else "Application"

    def resolve_app_key(self, raw_name: str) -> str | None:
        """Strictly map a requested application phrase to an app registry key."""
        if not raw_name:
            return None
        norm = raw_name.lower().strip()
        norm = re.sub(r"^(my|the|a|an|launch|open|start|run)\s+", "", norm).strip()
        norm = re.sub(r"\s+(app|application|program|software)$", "", norm).strip()

        # 1. Exact alias match
        if norm in self._alias_map:
            return self._alias_map[norm]

        # 2. Strict token/word boundary match
        for alias, key in self._alias_map.items():
            if re.search(rf"\b{re.escape(alias)}\b", norm) or norm == alias:
                return key

        return None

    def resolve_app_target(self, raw_name: str) -> ResolvedAppTarget:
        """Multi-Tier Discovery: Resolves requested application through 10 discovery mechanisms."""
        if not raw_name:
            return ResolvedAppTarget(
                canonical_name="Unknown",
                app_key="unknown",
                launch_type="none",
                target_path="",
                found=False,
                error_message="No application specified.",
            )

        clean_name = raw_name.strip()
        norm_name = re.sub(r"^(my|the|a|an|launch|open|start|run)\s+", "", clean_name.lower()).strip()
        norm_name = re.sub(r"\s+(app|application|program|software)$", "", norm_name).strip()

        app_key = self.resolve_app_key(clean_name)
        info = self._APP_REGISTRY.get(app_key, {}) if app_key else {}
        canonical_name = str(info.get("name", clean_name.title()))

        # Search candidates (executable names)
        exe_candidates = list(info.get("exes") or [])
        if not exe_candidates:
            exe_candidates = [f"{norm_name}.exe", f"{norm_name.replace(' ', '')}.exe"]

        shortcut_patterns = list(info.get("shortcuts") or [])
        if not shortcut_patterns:
            shortcut_patterns = [f"*{norm_name}*.lnk", f"*{clean_name}*.lnk"]

        # TIER 1: Windows App Paths Registry (HKLM & HKCU)
        if sys.platform.startswith("win"):
            for exe in exe_candidates:
                reg_path = self._query_app_paths_registry(exe)
                if reg_path and os.path.exists(reg_path):
                    logger.info("[APP RESOLUTION] Tier 1 App Paths Registry match for '%s': %s", clean_name, reg_path)
                    return ResolvedAppTarget(
                        canonical_name=canonical_name,
                        app_key=app_key or norm_name,
                        launch_type="exe",
                        target_path=reg_path,
                        found=True,
                        source="Windows App Paths Registry",
                    )

        # TIER 2: Windows Uninstall Registry (HKLM, HKCU, WOW6432Node)
        if sys.platform.startswith("win"):
            uninst_path = self._query_uninstall_registry(norm_name, exe_candidates)
            if uninst_path and os.path.exists(uninst_path):
                logger.info("[APP RESOLUTION] Tier 2 Uninstall Registry match for '%s': %s", clean_name, uninst_path)
                return ResolvedAppTarget(
                    canonical_name=canonical_name,
                    app_key=app_key or norm_name,
                    launch_type="exe",
                    target_path=uninst_path,
                    found=True,
                    source="Windows Uninstall Registry",
                )

        # TIER 3: Start Menu Shortcuts (.lnk)
        start_menu_dirs = [
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
        ]
        for pattern in shortcut_patterns:
            for sdir in start_menu_dirs:
                if not os.path.exists(sdir):
                    continue
                matches = glob.glob(os.path.join(sdir, "**", pattern), recursive=True)
                valid = [m for m in matches if not any(b in m.lower() for b in ("cccp", "codec", "uninstall", "installer"))]
                if valid:
                    shortcut_path = valid[0]
                    logger.info("[APP RESOLUTION] Tier 3 Start Menu match for '%s': %s", clean_name, shortcut_path)
                    return ResolvedAppTarget(
                        canonical_name=canonical_name,
                        app_key=app_key or norm_name,
                        launch_type="shortcut",
                        target_path=shortcut_path,
                        found=True,
                        source="Start Menu Shortcut",
                    )

        # TIER 4: Desktop Shortcuts (.lnk)
        desktop_dirs = [
            os.path.expandvars(r"%USERPROFILE%\Desktop"),
            os.path.expandvars(r"%PUBLIC%\Desktop"),
        ]
        for pattern in shortcut_patterns:
            for ddir in desktop_dirs:
                if not os.path.exists(ddir):
                    continue
                matches = glob.glob(os.path.join(ddir, pattern))
                if matches:
                    shortcut_path = matches[0]
                    logger.info("[APP RESOLUTION] Tier 4 Desktop Shortcut match for '%s': %s", clean_name, shortcut_path)
                    return ResolvedAppTarget(
                        canonical_name=canonical_name,
                        app_key=app_key or norm_name,
                        launch_type="shortcut",
                        target_path=shortcut_path,
                        found=True,
                        source="Desktop Shortcut",
                    )

        # TIER 5: Common Program Files & AppData Paths
        common_search_paths = [
            os.path.expandvars(r"%APPDATA%\Zoom\bin"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Teams\current"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft Office\root\Office16"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft Office\root\Office16"),
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft VS Code"),
            os.path.expandvars(r"%SystemRoot%\System32"),
            os.path.expandvars(r"%SystemRoot%"),
        ]
        for exe in exe_candidates:
            for spath in common_search_paths:
                candidate = os.path.join(spath, exe)
                if os.path.exists(candidate):
                    logger.info("[APP RESOLUTION] Tier 5 Common Path match for '%s': %s", clean_name, candidate)
                    return ResolvedAppTarget(
                        canonical_name=canonical_name,
                        app_key=app_key or norm_name,
                        launch_type="exe",
                        target_path=candidate,
                        found=True,
                        source="Known Executable Path",
                    )

        # TIER 6: System PATH Resolution (shutil.which)
        for exe in exe_candidates:
            found_path = shutil.which(exe)
            if found_path and os.path.exists(found_path):
                logger.info("[APP RESOLUTION] Tier 6 PATH match for '%s': %s", clean_name, found_path)
                return ResolvedAppTarget(
                    canonical_name=canonical_name,
                    app_key=app_key or norm_name,
                    launch_type="exe",
                    target_path=found_path,
                    found=True,
                    source="System PATH",
                )

        # TIER 7: URI Protocol Fallback (e.g. msteams:, zoommtg:, ms-powerpoint:, ms-word:, ms-excel:, calculator:, camera:)
        uri = info.get("uri")
        if uri:
            logger.info("[APP RESOLUTION] Tier 7 URI Protocol match for '%s': %s", clean_name, uri)
            return ResolvedAppTarget(
                canonical_name=canonical_name,
                app_key=app_key or norm_name,
                launch_type="uri",
                target_path=uri,
                found=True,
                source="Windows URI Protocol",
            )

        logger.warning("[APP RESOLUTION] Application '%s' could not be resolved.", clean_name)
        return ResolvedAppTarget(
            canonical_name=canonical_name,
            app_key=app_key or norm_name,
            launch_type="none",
            target_path="",
            found=False,
            error_message=f"Application '{canonical_name}' is not installed or resolvable on this computer.",
            source="None",
        )

    def _query_app_paths_registry(self, exe_name: str) -> str | None:
        """Query HKLM & HKCU App Paths registry for executable location."""
        if not sys.platform.startswith("win"):
            return None
        keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        ]
        for hkey, subkey in keys:
            try:
                with winreg.OpenKey(hkey, f"{subkey}\\{exe_name}") as k:
                    val, _ = winreg.QueryValueEx(k, "")
                    if val and os.path.exists(val):
                        return str(val)
            except Exception:
                pass
        return None

    def _query_uninstall_registry(self, norm_name: str, exe_candidates: list[str]) -> str | None:
        """Query Windows Uninstall Registry keys for matching application path."""
        if not sys.platform.startswith("win"):
            return None
        keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        for hkey, subkey in keys:
            try:
                with winreg.OpenKey(hkey, subkey) as k:
                    num, _, _ = winreg.QueryInfoKey(k)
                    for i in range(num):
                        try:
                            sub_name = winreg.EnumKey(k, i)
                            with winreg.OpenKey(k, sub_name) as app_k:
                                disp_name = ""
                                try:
                                    disp_name, _ = winreg.QueryValueEx(app_k, "DisplayName")
                                except Exception:
                                    pass
                                if norm_name in disp_name.lower():
                                    # Try DisplayIcon or InstallLocation
                                    loc = ""
                                    try:
                                        loc, _ = winreg.QueryValueEx(app_k, "InstallLocation")
                                    except Exception:
                                        pass
                                    if loc and os.path.exists(loc):
                                        for exe in exe_candidates:
                                            cand = os.path.join(loc, exe)
                                            if os.path.exists(cand):
                                                return cand
                                            # Subdirectory check
                                            sub_cand = glob.glob(os.path.join(loc, "**", exe), recursive=True)
                                            if sub_cand:
                                                return sub_cand[0]
                                    icon = ""
                                    try:
                                        icon, _ = winreg.QueryValueEx(app_k, "DisplayIcon")
                                    except Exception:
                                        pass
                                    if icon:
                                        icon_path = icon.split(",")[0].strip('"')
                                        if os.path.exists(icon_path) and icon_path.lower().endswith(".exe"):
                                            return icon_path
                        except Exception:
                            pass
            except Exception:
                pass
        return None

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
                "[APP LAUNCH SUCCESS] Requested: '%s' Resolved: '%s' Path: '%s' Method: %s Source: %s",
                target.canonical_name,
                target.canonical_name,
                target.target_path,
                target.launch_type,
                target.source,
            )
            return True, success_msg
        except Exception as exc:
            err_msg = f"Failed to launch {target.canonical_name}: {exc}"
            logger.exception("[APP LAUNCH ERROR] %s", err_msg)
            return False, err_msg

    def list_installed_applications(self) -> list[dict]:
        """Diagnostic tool: Enumerate all resolvable applications on the current system."""
        results = []
        for app_key in self._APP_REGISTRY:
            info = self._APP_REGISTRY[app_key]
            canonical_name = info["name"]
            target = self.resolve_app_target(canonical_name)
            results.append({
                "display_name": canonical_name,
                "app_key": app_key,
                "launch_type": target.launch_type,
                "source": target.source,
                "target_path": target.target_path,
                "resolvable": "YES" if target.found else "NO",
            })
        return results


# Singleton Instance
app_resolver = DesktopAppResolver()
