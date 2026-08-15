"""FilesystemTool providing workspace-bounded safe local file reading, searching, ranking, and candidate ambiguity resolution."""

from __future__ import annotations

from datetime import datetime, timedelta
import os
from pathlib import Path
from typing import Any

from backend.agent.policy_engine import PermissionLevel
from backend.agent.task_state import TaskState
from backend.agent.tool_registry import ToolDescriptor, ToolResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class FilesystemTool:
    """Safe Workspace-Bounded Filesystem Tool for IRIS AI."""

    def __init__(self, workspace_root: str | None = None) -> None:
        root_dir = workspace_root or os.getcwd()
        self._workspace_root = Path(root_dir).resolve()

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            tool_id="filesystem_tool",
            name="filesystem_tool",
            description="Reads workspace files, searches for files, ranks by recency/relevance, filters by file extension or modification date, and resolves candidate ambiguities safely.",
            permission_level=PermissionLevel.SAFE,
            input_schema={
                "action": "read_file | list_dir | search_files | file_exists | find_latest",
                "path": "Relative or absolute file/directory path",
                "query": "Search query or keyword",
                "extension": "File extension filter (e.g. '.pdf', '.md', '.gguf')",
                "modified_days": "Filter files modified within last N days (int)",
            },
            output_schema={"success": "bool", "message": "str", "data": "dict"},
        )

    def _resolve_safe_path(self, target_path_str: str) -> Path | None:
        """Resolve path and verify it stays within workspace_root boundary."""
        try:
            target = Path(target_path_str)
            if not target.is_absolute():
                target = self._workspace_root / target
            resolved = target.resolve()
            if self._workspace_root in resolved.parents or resolved == self._workspace_root:
                return resolved
            logger.warning("FilesystemTool rejected path outside workspace: %s", target_path_str)
            return None
        except Exception:
            return None

    def execute(self, params: dict[str, Any], task_state: TaskState | None = None) -> ToolResult:
        """Execute filesystem action."""
        action = str(params.get("action") or "search_files").lower().strip()
        path_str = str(params.get("path") or ".").strip()

        safe_path = self._resolve_safe_path(path_str)
        if safe_path is None:
            return ToolResult(False, f"Access denied: path '{path_str}' is outside workspace boundary", error_code="SECURITY_VIOLATION")

        if action in ("read_file", "read"):
            if not safe_path.is_file():
                return ToolResult(False, f"File not found: {path_str}", error_code="FILE_NOT_FOUND")
            try:
                content = safe_path.read_text(encoding="utf-8", errors="replace")
                if len(content) > 50000:
                    content = content[:50000] + "\n...[truncated]"
                return ToolResult(True, f"Read file '{safe_path.name}'", data={"content": content, "path": str(safe_path), "size": len(content)})
            except Exception as exc:
                return ToolResult(False, f"Failed to read file: {exc}")

        if action in ("list_dir", "list"):
            if not safe_path.is_dir():
                return ToolResult(False, f"Directory not found: {path_str}", error_code="DIR_NOT_FOUND")
            try:
                entries = []
                for child in safe_path.iterdir():
                    entries.append({
                        "name": child.name,
                        "is_dir": child.is_dir(),
                        "size": child.stat().st_size if child.is_file() else 0,
                    })
                return ToolResult(True, f"Listed {len(entries)} items in {safe_path.name}", data={"entries": entries, "path": str(safe_path)})
            except Exception as exc:
                return ToolResult(False, f"Failed to list directory: {exc}")

        if action in ("search_files", "search", "find_latest"):
            query = str(params.get("query") or "").lower().strip()
            ext_filter = str(params.get("extension") or "").lower().strip()
            if ext_filter and not ext_filter.startswith("."):
                ext_filter = f".{ext_filter}"

            mod_days = params.get("modified_days")
            cutoff_timestamp = None
            if mod_days is not None:
                try:
                    cutoff_timestamp = (datetime.now() - timedelta(days=float(mod_days))).timestamp()
                except Exception:
                    pass

            raw_matches = []
            try:
                search_root = safe_path if safe_path.is_dir() else self._workspace_root
                for root, _, files in os.walk(search_root):
                    for f_name in files:
                        full_p = Path(root) / f_name
                        rel_p = str(full_p.relative_to(self._workspace_root))
                        f_name_lower = f_name.lower()

                        # Apply filters
                        if ext_filter and not f_name_lower.endswith(ext_filter):
                            continue

                        stat_info = full_p.stat()
                        mtime = stat_info.st_mtime
                        if cutoff_timestamp and mtime < cutoff_timestamp:
                            continue

                        # Calculate relevance score
                        score = 0
                        if query:
                            if query == f_name_lower:
                                score += 100
                            elif query in f_name_lower:
                                score += 50
                            elif any(w in f_name_lower for w in query.split()):
                                score += 20
                            elif query in rel_p.lower():
                                score += 10
                            else:
                                continue
                        else:
                            score = 10

                        raw_matches.append({
                            "path": rel_p,
                            "name": f_name,
                            "mtime": mtime,
                            "mtime_str": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
                            "score": score,
                            "size": stat_info.st_size,
                        })

                # Sort by score desc, then mtime desc
                raw_matches.sort(key=lambda x: (x["score"], x["mtime"]), reverse=True)
                top_matches = raw_matches[:20]
                matches_paths = [m["path"] for m in top_matches]

                # Construct structured candidate list for candidate ambiguity resolution
                candidates = []
                for idx, item in enumerate(top_matches[:5], start=1):
                    candidates.append({
                        "index": idx,
                        "name": item["name"],
                        "path": item["path"],
                        "modified": item["mtime_str"],
                    })

                # Store candidates into task_state if provided
                if task_state and candidates:
                    task_state.last_resolved_target = candidates[0]["path"]

                msg = f"Found {len(top_matches)} matching files" if top_matches else "No matching files found"
                return ToolResult(
                    True,
                    msg,
                    data={
                        "matches": matches_paths,
                        "candidates": candidates,
                        "count": len(top_matches),
                        "has_multiple_candidates": len(candidates) > 1,
                    },
                )
            except Exception as exc:
                return ToolResult(False, f"Search failed: {exc}")

        if action in ("file_exists", "exists"):
            exists = safe_path.exists()
            return ToolResult(True, f"Path exists: {exists}", data={"exists": exists, "is_file": safe_path.is_file(), "is_dir": safe_path.is_dir()})

        return ToolResult(False, f"Unsupported filesystem action '{action}'")
