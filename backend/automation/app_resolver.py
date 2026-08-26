"""
Centralized Generalized Windows Desktop Application Resolver & Launcher for IRIS AI.
Dynamically discovers and resolves Win32, UWP/MSIX, Start Menu, Registry App Paths,
Uninstall Registry, running processes, top-level windows, and URI protocol applications
for hands-free Windows automation.
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
import winreg
from dataclasses import dataclass, field
from typing import Any

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Protected Windows and IRIS system processes that must never be terminated by voice commands.
PROTECTED_PROCESSES = {
    "system", "idle", "registry", "smss.exe", "csrss.exe", "wininit.exe",
    "services.exe", "lsass.exe", "svchost.exe", "fontdrvhost.exe", "dwm.exe",
    "explorer.exe", "sihost.exe", "taskhostw.exe", "runtimebroker.exe",
    "ctfmon.exe", "searchhost.exe", "startmenuexperiencehost.exe",
    "shellexperiencehost.exe", "textinputhost.exe", "python.exe", "pythonw.exe",
    "electron.exe", "iris_backend.exe", "iris ai.exe", "conhost.exe",
}

# Helper host/update binaries that should not be targeted instead of the main application.
HELPER_PROCESS_BLACKLIST = {
    "remoting_host.exe", "crashpad_handler.exe", "update.exe", "installer.exe",
    "setup.exe", "elevated.exe", "service.exe", "msedgewebview2.exe", "webview2.exe",
}


@dataclass
class ResolvedAppTarget:
    canonical_name: str
    app_key: str
    launch_type: str  # "exe", "shortcut", "uri", "shell", "system"
    target_path: str
    found: bool = True
    error_message: str | None = None
    source: str = "Unknown"


@dataclass
class ResolvedRunningApp:
    matched: bool
    name: str
    process_names: list[str] = field(default_factory=list)
    pids: list[int] = field(default_factory=list)
    window_handles: list[int] = field(default_factory=list)
    source: str = "none"


def get_pe_metadata(exe_path: str) -> dict[str, str]:
    """Retrieve FileDescription and ProductName from Win32 PE metadata."""
    if not exe_path or not os.path.exists(exe_path) or not sys.platform.startswith("win"):
        return {}
    try:
        import win32api
        lang, codepage = win32api.GetFileVersionInfo(exe_path, "\\VarFileInfo\\Translation")[0]
        str_info_path = f"\\StringFileInfo\\{lang:04x}{codepage:04x}\\"
        desc = str(win32api.GetFileVersionInfo(exe_path, str_info_path + "FileDescription") or "").strip()
        prod = str(win32api.GetFileVersionInfo(exe_path, str_info_path + "ProductName") or "").strip()
        return {"description": desc, "product": prod}
    except Exception:
        return {}


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
            "aliases": ("microsoft powerpoint", "ms powerpoint", "power point", "powerpoint", "ppt", "presentation", "slides"),
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
            "aliases": ("file explorer", "explorer", "files", "this pc", "my computer", "computer", "windows explorer"),
            "exes": ("explorer.exe",),
            "shortcuts": ("*File Explorer*.lnk",),
            "uri": None,
        },
        "settings": {
            "name": "Windows Settings",
            "aliases": ("settings", "windows settings", "system settings", "setting"),
            "exes": ("SystemSettings.exe",),
            "shortcuts": (),
            "uri": "ms-settings:",
            "prefer_uri": True,
        },
        "controlpanel": {
            "name": "Control Panel",
            "aliases": ("control panel", "control"),
            "exes": ("control.exe",),
            "shortcuts": ("*Control Panel*.lnk",),
            "uri": None,
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
            "exes": ("Code.exe", "code.exe", "code.cmd"),
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
        "discord": {
            "name": "Discord",
            "aliases": ("discord", "discord app"),
            "exes": ("Discord.exe",),
            "shortcuts": ("*Discord*.lnk",),
            "uri": "discord:",
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
        clean = raw_name.strip()
        return clean.title() if clean else "Application"

    def resolve_app_key(self, raw_name: str) -> str | None:
        """Strictly map a requested application phrase to an app registry key."""
        if not raw_name:
            return None
        norm = raw_name.lower().strip()
        norm = re.sub(r"^(my|the|a|an|launch|open|start|run|close|quit|exit|kill|stop)\s+", "", norm).strip()
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
        """Multi-Tier Discovery: Resolves requested application through dynamic discovery mechanisms."""
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
        norm_name = re.sub(r"^(my|the|a|an|launch|open|start|run|close|quit|exit|kill|stop)\s+", "", clean_name.lower()).strip()
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

        # TIER 0: Native Windows URI Protocol (Priority override for Settings and URI-preferred apps)
        if info.get("prefer_uri") or (info.get("uri") and (app_key == "settings" or norm_name in ("settings", "windows settings", "system settings", "setting"))):
            uri = info.get("uri") or "ms-settings:"
            logger.info("[APP RESOLUTION] Tier 0 Native URI Protocol match for '%s': %s", clean_name, uri)
            return ResolvedAppTarget(
                canonical_name=canonical_name,
                app_key=app_key or norm_name,
                launch_type="uri",
                target_path=uri,
                found=True,
                source="Windows URI Protocol",
            )

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

        # TIER 3: Start Menu Shortcuts (.lnk) - Search patterns & dynamic scan
        start_menu_dirs = [
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
        ]
        for pattern in shortcut_patterns:
            for sdir in start_menu_dirs:
                if not os.path.exists(sdir):
                    continue
                matches = glob.glob(os.path.join(sdir, "**", pattern), recursive=True)
                valid = [m for m in matches if not any(b in m.lower() for b in ("cccp", "codec", "uninstall", "installer", "setup"))]
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

        # Dynamic Start Menu scan for arbitrary application names
        for sdir in start_menu_dirs:
            if not os.path.exists(sdir):
                continue
            for f in glob.glob(os.path.join(sdir, "**", "*.lnk"), recursive=True):
                base = os.path.splitext(os.path.basename(f))[0].lower()
                if any(b in base for b in ("uninstall", "install", "setup", "help", "readme", "documentation")):
                    continue
                if norm_name == base or re.search(rf"\b{re.escape(norm_name)}\b", base):
                    logger.info("[APP RESOLUTION] Tier 3 Dynamic Start Menu match for '%s': %s", clean_name, f)
                    return ResolvedAppTarget(
                        canonical_name=os.path.splitext(os.path.basename(f))[0],
                        app_key=app_key or norm_name,
                        launch_type="shortcut",
                        target_path=f,
                        found=True,
                        source="Dynamic Start Menu Shortcut",
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
            os.path.expandvars(r"%LOCALAPPDATA%\Discord\app-*"),
            os.path.expandvars(r"%APPDATA%\Spotify"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps"),
            os.path.expandvars(r"%SystemRoot%\System32"),
            os.path.expandvars(r"%SystemRoot%"),
        ]
        for exe in exe_candidates:
            for spath in common_search_paths:
                if "*" in spath:
                    matches = glob.glob(os.path.join(spath, exe))
                    if matches and os.path.exists(matches[0]):
                        logger.info("[APP RESOLUTION] Tier 5 Common Path match for '%s': %s", clean_name, matches[0])
                        return ResolvedAppTarget(
                            canonical_name=canonical_name,
                            app_key=app_key or norm_name,
                            launch_type="exe",
                            target_path=matches[0],
                            found=True,
                            source="Known Executable Path",
                        )
                else:
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

        # TIER 7: URI Protocol Fallback
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
            error_message=f"Sir, I couldn't find {canonical_name} on this computer.",
            source="None",
        )

    def resolve_running_app(self, raw_name: str) -> ResolvedRunningApp:
        """Dynamically resolve running processes and top-level windows for any requested application.

        Uses:
        1. Discovered executable paths from installed app resolver.
        2. Known registry aliases and executable candidates.
        3. Running process image names (psutil).
        4. PE File Version metadata (FileDescription & ProductName).
        5. Top-level visible window titles.
        """
        if not raw_name or not raw_name.strip():
            return ResolvedRunningApp(matched=False, name="Unknown")

        clean_name = raw_name.strip()
        norm_name = re.sub(r"^(my|the|a|an|close|quit|exit|kill|stop)\s+", "", clean_name.lower()).strip()
        norm_name = re.sub(r"\s+(app|application|program|software)$", "", norm_name).strip()

        # If target is a special bare window
        if norm_name in ("window", "active window", "focused window", "this window"):
            return ResolvedRunningApp(matched=True, name="Window", source="active_window")

        app_key = self.resolve_app_key(clean_name)

        # Special handler for File Explorer to detect folder windows without terminating the desktop shell
        if norm_name in ("explorer", "file explorer", "files", "this pc", "my computer", "windows explorer") or app_key in ("explorer", "file_explorer"):
            if sys.platform.startswith("win"):
                explorer_hwnds, explorer_pids = self._find_explorer_windows()
                if explorer_hwnds:
                    return ResolvedRunningApp(
                        matched=True,
                        name="File Explorer",
                        process_names=["explorer.exe"],
                        pids=explorer_pids,
                        window_handles=explorer_hwnds,
                        source="explorer_window_match",
                    )
                return ResolvedRunningApp(
                    matched=False,
                    name="File Explorer",
                    source="none",
                )

        # Query installed application metadata to establish canonical display name
        resolved_installed = self.resolve_app_target(clean_name)
        canonical_name = resolved_installed.canonical_name if resolved_installed and resolved_installed.found else clean_name.title()

        # Exclude protected processes
        if norm_name in PROTECTED_PROCESSES or f"{norm_name}.exe" in PROTECTED_PROCESSES:
            logger.warning("[CLOSE SECURITY] Attempt to target protected process '%s' rejected.", norm_name)
            return ResolvedRunningApp(matched=False, name=canonical_name, source="protected_process")

        # Collect running processes (with psutil or tasklist fallback)
        running_procs: list[tuple[int, str, str]] = []
        try:
            import psutil
            for p in psutil.process_iter(["pid", "name", "exe"]):
                try:
                    info = p.info
                    pname = (info["name"] or "").strip()
                    exe = (info["exe"] or "").strip()
                    pid = info["pid"]
                    if not pname or pname.lower() in PROTECTED_PROCESSES or pname.lower() in HELPER_PROCESS_BLACKLIST:
                        continue
                    running_procs.append((pid, pname, exe))
                except Exception:
                    pass
        except (ImportError, Exception):
            if sys.platform.startswith("win"):
                try:
                    import csv
                    import io
                    completed = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, check=False)
                    reader = csv.reader(io.StringIO(completed.stdout or ""))
                    for row in reader:
                        if len(row) >= 2:
                            pname = row[0].strip()
                            if pname.lower() not in PROTECTED_PROCESSES and pname.lower() not in HELPER_PROCESS_BLACKLIST:
                                try:
                                    running_procs.append((int(row[1].strip()), pname, ""))
                                except ValueError:
                                    pass
                except Exception:
                    pass

        # Centralized mapping from friendly/spoken application names to exact Windows executables
        FRIENDLY_EXE_MAP: dict[str, str] = {
            "microsoft word": "winword.exe",
            "word": "winword.exe",
            "winword": "winword.exe",
            "microsoft powerpoint": "powerpnt.exe",
            "power point": "powerpnt.exe",
            "powerpoint": "powerpnt.exe",
            "ppt": "powerpnt.exe",
            "microsoft excel": "excel.exe",
            "excel": "excel.exe",
            "file explorer": "explorer.exe",
            "explorer": "explorer.exe",
            "files": "explorer.exe",
            "this pc": "explorer.exe",
            "my computer": "explorer.exe",
            "windows explorer": "explorer.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "notepad": "notepad.exe",
            "chrome": "chrome.exe",
            "google chrome": "chrome.exe",
            "edge": "msedge.exe",
            "microsoft edge": "msedge.exe",
            "teams": "ms-teams.exe",
            "microsoft teams": "ms-teams.exe",
            "spotify": "spotify.exe",
            "discord": "discord.exe",
        }

        # 1. Check known executable candidates from friendly name map and app discovery
        known_exes = set()
        mapped_exe = FRIENDLY_EXE_MAP.get(norm_name) or FRIENDLY_EXE_MAP.get(clean_name.lower())
        if mapped_exe:
            known_exes.add(mapped_exe.lower())

        if resolved_installed and resolved_installed.found and resolved_installed.target_path:
            base_exe = os.path.basename(resolved_installed.target_path).lower()
            if base_exe.endswith(".exe"):
                known_exes.add(base_exe)

        app_key = self.resolve_app_key(clean_name)
        if app_key and app_key in self._APP_REGISTRY:
            reg_entry = self._APP_REGISTRY[app_key]
            for e in reg_entry.get("exes", ()):
                known_exes.add(e.lower())

        if known_exes:
            matching_pids: list[int] = []
            matching_names: set[str] = set()
            for pid, pname, exe in running_procs:
                if pname.lower() in known_exes:
                    matching_pids.append(pid)
                    matching_names.add(pname)
            if matching_pids:
                return ResolvedRunningApp(
                    matched=True,
                    name=canonical_name,
                    process_names=list(matching_names),
                    pids=matching_pids,
                    source="installed_app_executable_match",
                )

        # 2. Exact or normalized process name match
        exact_candidates = {f"{norm_name}.exe", norm_name, f"{norm_name.replace(' ', '')}.exe"}
        matching_pids = []
        matching_names = set()
        for pid, pname, exe in running_procs:
            if pname.lower() in exact_candidates:
                matching_pids.append(pid)
                matching_names.add(pname)
        if matching_pids:
            return ResolvedRunningApp(
                matched=True,
                name=canonical_name,
                process_names=list(matching_names),
                pids=matching_pids,
                source="exact_process_name_match",
            )

        # 3. PE Executable Metadata (FileDescription / ProductName)
        for pid, pname, exe in running_procs:
            meta = get_pe_metadata(exe)
            desc = meta.get("description", "").lower()
            prod = meta.get("product", "").lower()
            if not desc and not prod:
                continue

            # Strict word boundary or equality match
            if (norm_name == desc or norm_name == prod or
                re.search(rf"\b{re.escape(norm_name)}\b", desc) or
                re.search(rf"\b{re.escape(norm_name)}\b", prod)):
                # Disambiguation safety guards
                if "edge" in norm_name and "chrome" in desc:
                    continue
                if "chrome" in norm_name and "edge" in desc:
                    continue
                matching_pids.append(pid)
                matching_names.add(pname)

        if matching_pids:
            return ResolvedRunningApp(
                matched=True,
                name=canonical_name,
                process_names=list(matching_names),
                pids=matching_pids,
                source="pe_metadata_match",
            )

        # 4. Top-Level Visible Window Titles (ctypes / Win32)
        if sys.platform.startswith("win"):
            window_pids = self._find_pids_by_window_title(norm_name, running_procs)
            if window_pids:
                pnames = list({pname for pid, pname, _ in running_procs if pid in window_pids})
                return ResolvedRunningApp(
                    matched=True,
                    name=canonical_name,
                    process_names=pnames,
                    pids=window_pids,
                    source="window_title_match",
                )

        return ResolvedRunningApp(
            matched=False,
            name=canonical_name,
            source="none",
        )

    def _find_explorer_windows(self) -> tuple[list[int], list[int]]:
        """Find visible top-level Windows File Explorer windows (CabinetWClass / ExploreWClass)."""
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32

            hwnds: list[int] = []
            pids: list[int] = []

            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def _enum_proc(hwnd: int, _lparam: int) -> bool:
                if not user32.IsWindowVisible(hwnd):
                    return True
                if user32.GetWindow(hwnd, 4):  # GW_OWNER = 4
                    return True
                class_buf = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, class_buf, 256)
                class_name = class_buf.value.strip()

                if class_name in ("CabinetWClass", "ExploreWClass"):
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    hwnds.append(int(hwnd))
                    if pid.value not in pids:
                        pids.append(pid.value)
                return True

            user32.EnumWindows(_enum_proc, 0)
            return hwnds, pids
        except Exception:
            return [], []

    def _find_pids_by_window_title(self, norm_name: str, running_procs: list[tuple[int, str, str]]) -> list[int]:
        """Match visible top-level windows against the normalized application name."""
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32

            matching_pids: list[int] = []
            running_pid_set = {pid for pid, _, _ in running_procs}

            # Build search terms for case-insensitive partial window title matching
            search_terms = [norm_name]
            if norm_name.startswith("microsoft "):
                search_terms.append(norm_name.replace("microsoft ", "").strip())
            if norm_name.startswith("ms "):
                search_terms.append(norm_name.replace("ms ", "").strip())
            if " " in norm_name:
                search_terms.append(norm_name.replace(" ", ""))

            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def _enum_proc(hwnd: int, _lparam: int) -> bool:
                if not user32.IsWindowVisible(hwnd):
                    return True
                if user32.GetWindow(hwnd, 4):  # GW_OWNER = 4
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length <= 0:
                    return True
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.strip().lower()
                if not title:
                    return True

                # Case-insensitive partial match for any search term within window title
                if any(term in title for term in search_terms if term):
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if (not running_pid_set or pid.value in running_pid_set) and pid.value not in matching_pids:
                        matching_pids.append(pid.value)
                return True

            user32.EnumWindows(_enum_proc, 0)
            return matching_pids
        except Exception:
            return []

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
                if sys.platform.startswith("win"):
                    try:
                        os.startfile(target.target_path)
                    except Exception:
                        subprocess.Popen([target.target_path], shell=True)
                else:
                    subprocess.Popen([target.target_path])
            elif target.launch_type == "uri":
                if sys.platform.startswith("win"):
                    try:
                        os.startfile(target.target_path)
                    except Exception:
                        subprocess.Popen(["cmd", "/c", "start", "", target.target_path])
                else:
                    subprocess.Popen(["open", target.target_path])
            else:
                if sys.platform.startswith("win"):
                    try:
                        os.startfile(target.target_path)
                    except Exception:
                        subprocess.Popen([target.target_path], shell=True)
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
