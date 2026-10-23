"""Local Document Search Engine and background search service for IRIS AI."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import threading
import time
from typing import Any, Callable

from backend.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_EXCLUDED_DIRS = {
    "$recycle.bin",
    "system volume information",
    "windows",
    "program files",
    "program files (x86)",
    "appdata",
    "temp",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
}

DEFAULT_SUPPORTED_FORMATS = {
    ".txt",
    ".md",
    ".log",
    ".py",
    ".csv",
    ".pdf",
    ".docx",
}

MAX_SNIPPET_LENGTH = 200


def open_document(target_path: str | Path, select_in_explorer: bool = True) -> bool:
    """
    Launches Windows File Explorer.
    If select_in_explorer=True and target is a file, opens Explorer with the file selected/highlighted.
    If target is a folder, opens the folder directly in Explorer.
    """
    path = Path(target_path).resolve()
    if not path.exists():
        logger.warning("[DOC_SEARCH] Cannot open path; path does not exist: %s", path)
        return False
    try:
        norm_path = os.path.normpath(str(path))
        if path.is_file() and select_in_explorer:
            subprocess.Popen(f'explorer /select,"{norm_path}"')
        else:
            subprocess.Popen(f'explorer "{norm_path}"')
        logger.info("[DOC_SEARCH] Opened path in Windows Explorer: %s (select=%s)", norm_path, select_in_explorer)
        return True
    except Exception as e:
        logger.error("[DOC_SEARCH] Failed to open path %s in explorer: %s", target_path, e)
        return False



class DocumentSearcher:
    """
    Local Document Search Engine.
    Scans supported file formats (.txt, .md, .log, .py, .csv, .pdf, .docx),
    extracting matching snippets and locations while excluding heavy/system directories.
    Supports multi-root target directories across core user folders and secondary drives.
    """

    EXCLUDED_DIRS = DEFAULT_EXCLUDED_DIRS

    def __init__(
        self,
        target_dirs: Path | str | list[Path | str] | None = None,
        max_results: int = 5,
        max_snippets_per_file: int = 3,
        excluded_dirs: set[str] | list[str] | None = None,
        supported_formats: set[str] | list[str] | None = None,
        target_dir: Path | str | None = None,
    ) -> None:
        effective_target = target_dirs if target_dirs is not None else target_dir

        if effective_target is None:
            home = Path.home()
            self.target_dirs = [
                home / "Documents",
                home / "Desktop",
                home / "Downloads",
            ]
            # Check for secondary data drives (D:\, E:\)
            for drive_letter in ["D", "E"]:
                drive_path = Path(f"{drive_letter}:\\")
                if drive_path.exists():
                    self.target_dirs.append(drive_path)
        elif isinstance(effective_target, (str, Path)):
            self.target_dirs = [Path(effective_target)]
        else:
            self.target_dirs = [Path(d) for d in effective_target]

        self.max_results = max_results
        self.max_snippets_per_file = max_snippets_per_file
        self.EXCLUDED_DIRS = {d.lower() for d in (excluded_dirs if excluded_dirs is not None else DEFAULT_EXCLUDED_DIRS)}
        self.excluded_dirs = self.EXCLUDED_DIRS
        self.supported_formats = (
            {ext.lower() for ext in supported_formats}
            if supported_formats is not None
            else set(DEFAULT_SUPPORTED_FORMATS)
        )

    @property
    def target_dir(self) -> Path:
        """Backwards compatibility accessor for the primary target directory."""
        return self.target_dirs[0] if self.target_dirs else Path.home() / "Documents"

    @target_dir.setter
    def target_dir(self, value: Path | str) -> None:
        self.target_dirs = [Path(value)]

    @staticmethod
    def _matches_name(name: str, query_lower: str) -> bool:
        """Check if name matches query, supporting space/underscore/hyphen variation."""
        nl = name.lower()
        if query_lower in nl:
            return True
        if " " in query_lower:
            if query_lower.replace(" ", "_") in nl or query_lower.replace(" ", "-") in nl:
                return True
            q_words = query_lower.split()
            if all(w in nl for w in q_words):
                return True
        return False

    @classmethod
    def _match_rank(cls, name: str, query_lower: str) -> int:
        """
        Rank matches for prioritization:
        0 = Exact match (e.g., 'MPC.txt' or folder 'MPC' for query 'mpc')
        1 = Prefix match (e.g., 'MPC_v2.txt' or 'MPC-report')
        2 = Substring match (e.g., 'sample_mpc_v2.log')
        """
        nl = name.lower()
        sl = Path(name).stem.lower()
        q_compact = query_lower.replace(" ", "").replace("_", "").replace("-", "")
        nl_compact = nl.replace(" ", "").replace("_", "").replace("-", "")
        sl_compact = sl.replace(" ", "").replace("_", "").replace("-", "")

        if nl == query_lower or sl == query_lower or sl_compact == q_compact or nl_compact == q_compact:
            return 0
        if nl.startswith(query_lower) or sl.startswith(query_lower) or sl_compact.startswith(q_compact):
            return 1
        return 2

    def _iter_candidate_files(self, timeout_seconds: float | None = None, start_time: float | None = None):
        """Yield candidate file paths across target directories (for backward compatibility)."""
        seen_paths: set[str] = set()
        for root_dir in self.target_dirs:
            try:
                if not root_dir.exists():
                    continue
                if root_dir.is_file():
                    yield root_dir
                    continue
                for root, dirs, files in os.walk(root_dir, topdown=True, followlinks=False):
                    dirs[:] = [d for d in dirs if d.lower() not in self.EXCLUDED_DIRS and not d.startswith(('.', '$'))]
                    for f in files:
                        if not f.startswith(('.', '$')):
                            yield Path(root) / f
            except (PermissionError, OSError):
                continue

    def _collect_candidate_files(self) -> list[Path]:
        """Collect all candidate files as a list."""
        return list(self._iter_candidate_files())

    def search(self, query: str, timeout_seconds: float = 8.0) -> list[dict[str, Any]]:
        """
        Search strictly by file and folder name across candidate directories.
        Bypasses file body content inspection entirely.
        Returns list of structured metadata:
        [
            {
                "file_name": "MPC.txt",
                "file_path": "C:\\Users\\...\\MPC.txt",
                "is_directory": False,
                "matches": [{"location": "Filename", "snippet": "C:\\Users\\...\\MPC.txt"}]
            }
        ]
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        query_lower = clean_query.lower()
        results: list[dict[str, Any]] = []
        seen_paths: set[str] = set()
        start_time = time.time()

        for root_dir in self.target_dirs:
            if (time.time() - start_time) > timeout_seconds:
                logger.warning(
                    "[DOC_SEARCH] Search elapsed time exceeded %.1fs timeout. Returning %d matches.",
                    timeout_seconds,
                    len(results),
                )
                break
            try:
                if not root_dir.exists():
                    continue
            except (PermissionError, OSError):
                continue

            if root_dir.is_file():
                if self._matches_name(root_dir.name, query_lower):
                    try:
                        resolved_str = str(root_dir.resolve())
                    except (PermissionError, OSError):
                        resolved_str = str(root_dir)
                    if resolved_str not in seen_paths:
                        seen_paths.add(resolved_str)
                        results.append({
                            "file_name": root_dir.name,
                            "file_path": resolved_str,
                            "is_directory": False,
                            "matches": [{"location": "Filename", "snippet": resolved_str}],
                        })
                        if len(results) >= self.max_results:
                            break
                continue

            try:
                for root, dirs, files in os.walk(root_dir, topdown=True, followlinks=False):
                    if (time.time() - start_time) > timeout_seconds:
                        logger.warning("[DOC_SEARCH] Directory traversal hit timeout %.1fs. Halting scan.", timeout_seconds)
                        break

                    # In-place directory exclusion
                    dirs[:] = [
                        d for d in dirs
                        if d.lower() not in self.EXCLUDED_DIRS
                        and not d.startswith(('.', '$'))
                    ]

                    root_path = Path(root)
                    if root_path.is_symlink():
                        continue

                    # 1. Match directories
                    sorted_dirs = sorted(dirs, key=lambda d: self._match_rank(d, query_lower))
                    for d in sorted_dirs:
                        if self._matches_name(d, query_lower):
                            folder_path = root_path / d
                            try:
                                resolved_str = str(folder_path.resolve())
                            except (PermissionError, OSError):
                                resolved_str = str(folder_path)
                            if resolved_str not in seen_paths:
                                seen_paths.add(resolved_str)
                                results.append({
                                    "file_name": d,
                                    "file_path": resolved_str,
                                    "is_directory": True,
                                    "matches": [{"location": "Folder", "snippet": resolved_str}],
                                })
                                if len(results) >= self.max_results:
                                    break
                    if len(results) >= self.max_results:
                        break

                    # 2. Match files
                    sorted_files = sorted(files, key=lambda f: self._match_rank(f, query_lower))
                    for f in sorted_files:
                        if f.startswith(('.', '$')):
                            continue
                        if self._matches_name(f, query_lower):
                            file_path = root_path / f
                            if self.supported_formats is not None and file_path.suffix.lower() not in self.supported_formats:
                                continue
                            try:
                                resolved_str = str(file_path.resolve())
                            except (PermissionError, OSError):
                                resolved_str = str(file_path)
                            if resolved_str not in seen_paths:
                                seen_paths.add(resolved_str)
                                results.append({
                                    "file_name": f,
                                    "file_path": resolved_str,
                                    "is_directory": False,
                                    "matches": [{"location": "Filename", "snippet": resolved_str}],
                                })
                                if len(results) >= self.max_results:
                                    break
                    if len(results) >= self.max_results:
                        break
            except (PermissionError, OSError):
                continue
            except Exception as err:
                logger.debug("[DOC_SEARCH] Unexpected error walking %s: %s", root_dir, err)
                continue

            if len(results) >= self.max_results:
                break

        # Prioritize exact matches (e.g., MPC.txt or folder MPC ranks higher than sample_mpc_v2.log)
        results.sort(key=lambda r: self._match_rank(r["file_name"], query_lower))
        return results[:self.max_results]



class DocumentSearchService:
    """
    Non-blocking async/daemon threaded document search service.
    Orchestrates acknowledgment speech, background execution, completion speech,
    voice recognition busy locking, UI conversation log event publishing,
    WebSocket event broadcasting, and file opening.
    """

    def __init__(
        self,
        searcher: DocumentSearcher | None = None,
        speech_manager: Any | None = None,
        broadcast_callback: Callable[[dict[str, Any]], None] | None = None,
        event_bus: Any | None = None,
        voice_service: Any | None = None,
    ) -> None:
        self.searcher = searcher or DocumentSearcher()
        self.speech_manager = speech_manager
        self.broadcast_callback = broadcast_callback
        self.event_bus = event_bus
        self.voice_service = voice_service
        self.last_results: list[dict[str, Any]] = []
        self.latest_result_path: str | None = None
        self._lock = threading.Lock()

    def set_speech_manager(self, speech_manager: Any) -> None:
        with self._lock:
            self.speech_manager = speech_manager

    def set_broadcast_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            self.broadcast_callback = callback

    def set_event_bus(self, event_bus: Any) -> None:
        with self._lock:
            self.event_bus = event_bus

    def set_voice_service(self, voice_service: Any) -> None:
        with self._lock:
            self.voice_service = voice_service

    def search_async(
        self,
        query: str,
        acknowledge: bool = True,
        on_complete: Callable[[list[dict[str, Any]]], None] | None = None,
    ) -> threading.Thread:
        """
        Trigger asynchronous search in a daemon thread.
        Sets voice recognizer busy lock to ignore background audio, speaks acknowledgment
        immediately on trigger, executes search with timeout guard, pushes assistant message
        to conversation log, speaks completion, and broadcasts WebSocket payload.
        """
        clean_query = query.strip()

        # Engage voice service busy lock so incoming microphone buffers are ignored
        with self._lock:
            vs = self.voice_service
        if vs is not None and hasattr(vs, "set_busy"):
            try:
                vs.set_busy(True)
            except Exception as vs_err:
                logger.debug("[DOC_SEARCH] Error setting voice_service busy: %s", vs_err)

        # Step A: Acknowledge search immediately
        if acknowledge:
            ack_message = f"Searching documents for {clean_query}."
            self._speak(ack_message)

        def _worker():
            try:
                results = self.searcher.search(clean_query, timeout_seconds=8.0)
                with self._lock:
                    self.last_results = results
                    if results:
                        self.latest_result_path = results[0]["file_path"]
                    else:
                        self.latest_result_path = None

                if results and self.latest_result_path:
                    # Auto-reveal top match in Windows File Explorer
                    open_document(self.latest_result_path, select_in_explorer=True)

                # Step B: Format assistant message for UI log and TTS completion
                if not results:
                    completion_msg = f"I couldn't find any documents mentioning {clean_query}."
                    ui_msg = f"No documents found matching '{clean_query}' across Desktop, Documents, or Downloads."
                else:
                    count = len(results)
                    top_file = results[0]["file_name"]
                    completion_msg = f"Found matching item {top_file}."
                    bullet_lines = []
                    for item in results:
                        fname = item.get("file_name", "")
                        fpath = item.get("file_path", "")
                        if item.get("is_directory"):
                            bullet_lines.append(f"• 📁 [Folder] {fname} ({fpath})")
                        else:
                            bullet_lines.append(f"• 📄 {fname} ({fpath})")
                    if bullet_lines:
                        ui_msg = f"Found matches for '{clean_query}' in {count} item(s):\n" + "\n".join(bullet_lines)
                    else:
                        ui_msg = f"Found matches for '{clean_query}' in {count} item(s)."

                # Step C: Publish assistant message event to EventBus / UI conversation log
                with self._lock:
                    bus = self.event_bus
                if bus is not None:
                    try:
                        from backend.voice.telemetry import AutomationExecutedEvent
                        bus.publish(
                            AutomationExecutedEvent(
                                intent="DOCUMENT_SEARCH",
                                action="DOCUMENT_SEARCH",
                                success=bool(results),
                                execution_status=ui_msg,
                            )
                        )
                    except Exception as ev_err:
                        logger.debug("[DOC_SEARCH] Error publishing AutomationExecutedEvent: %s", ev_err)

                # Step D: Broadcast WebSocket event
                event_data = {
                    "event_type": "DOCUMENT_SEARCH_RESULTS",
                    "query": clean_query,
                    "count": len(results),
                    "results": results,
                    "top_result": results[0] if results else None,
                    "message": ui_msg,
                    "execution_status": ui_msg,
                    "timestamp": time.time(),
                }
                self._broadcast(event_data)

                # Step E: Completion speech
                self._speak(completion_msg)

                if on_complete is not None:
                    try:
                        on_complete(results)
                    except Exception as exc:
                        logger.debug("[DOC_SEARCH] on_complete callback error: %s", exc)
            except Exception as err:
                logger.error("[DOC_SEARCH] Background search error: %s", err, exc_info=True)
            finally:
                # Reset voice service busy lock after search, UI broadcast, and completion TTS
                with self._lock:
                    vs_exit = self.voice_service
                if vs_exit is not None and hasattr(vs_exit, "set_busy"):
                    try:
                        vs_exit.set_busy(False)
                    except Exception as vs_err:
                        logger.debug("[DOC_SEARCH] Error resetting voice_service busy: %s", vs_err)

        thread = threading.Thread(target=_worker, name=f"DocSearch-{clean_query[:15]}", daemon=True)
        thread.start()
        return thread

    def open_latest_top_result(self) -> bool:
        """Open the top result from the most recent search."""
        with self._lock:
            if not self.last_results:
                logger.info("[DOC_SEARCH] No recent search results to open.")
                self._speak("No recent search results to open.")
                return False
            top_file_path = self.latest_result_path or (self.last_results[0].get("file_path", "") if self.last_results else "")
            top_file_name = self.last_results[0].get("file_name", "document") if self.last_results else "document"

        if top_file_path:
            self._speak(f"Opening {top_file_name}.")
            return open_document(top_file_path, select_in_explorer=True)
        return False

    def _speak(self, text: str) -> None:
        sm = self.speech_manager
        if sm is not None and hasattr(sm, "speak"):
            try:
                sm.speak(text)
            except Exception as err:
                logger.debug("[DOC_SEARCH] Speech output failed: %s", err)

    def _broadcast(self, event_data: dict[str, Any]) -> None:
        cb = self.broadcast_callback
        if cb is not None:
            try:
                cb(event_data)
            except Exception as err:
                logger.debug("[DOC_SEARCH] Broadcast callback failed: %s", err)


# Global singleton instance for app-wide coordination
document_search_service = DocumentSearchService()

