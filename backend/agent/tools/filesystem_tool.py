"""FilesystemTool providing workspace-bounded safe local file reading, searching, and directory listing."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from backend.agent.policy_engine import PermissionLevel
from backend.agent.task_state import TaskState
from backend.agent.tool_registry import ToolDescriptor, ToolResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class FilesystemTool:
    """Safe Workspace-Bounded Filesystem Tool."""

    def __init__(self, workspace_root: str | None = None) -> None:
        root_dir = workspace_root or os.getcwd()
        self._workspace_root = Path(root_dir).resolve()

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            tool_id="filesystem_tool",
            name="filesystem_tool",
            description="Reads workspace files, lists directories, searches for files, and checks file paths safely.",
            permission_level=PermissionLevel.SAFE,
            input_schema={
                "action": "read_file | list_dir | search_files | file_exists",
                "path": "Relative or absolute file/directory path",
                "query": "Search query or pattern",
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
        action = str(params.get("action") or "").lower().strip()
        path_str = str(params.get("path") or ".").strip()

        safe_path = self._resolve_safe_path(path_str)
        if safe_path is None:
            return ToolResult(False, f"Access denied: path '{path_str}' is outside workspace boundary", error_code="SECURITY_VIOLATION")

        if action == "read_file" or action == "read":
            if not safe_path.is_file():
                return ToolResult(False, f"File not found: {path_str}", error_code="FILE_NOT_FOUND")
            try:
                content = safe_path.read_text(encoding="utf-8", errors="replace")
                # Truncate large files if > 50KB to keep memory light
                if len(content) > 50000:
                    content = content[:50000] + "\n...[truncated]"
                return ToolResult(True, f"Read file {safe_path.name}", data={"content": content, "path": str(safe_path), "size": len(content)})
            except Exception as exc:
                return ToolResult(False, f"Failed to read file: {exc}")

        if action == "list_dir" or action == "list":
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

        if action == "search_files" or action == "search":
            query = str(params.get("query") or "").lower().strip()
            if not query:
                return ToolResult(False, "Search query missing")
            matches = []
            try:
                for root, _, files in os.walk(safe_path):
                    for file in files:
                        if query in file.lower():
                            full_p = Path(root) / file
                            rel_p = str(full_p.relative_to(self._workspace_root))
                            matches.append(rel_p)
                            if len(matches) >= 25:
                                break
                    if len(matches) >= 25:
                        break
                return ToolResult(True, f"Found {len(matches)} files matching '{query}'", data={"matches": matches})
            except Exception as exc:
                return ToolResult(False, f"Search failed: {exc}")

        if action == "file_exists" or action == "exists":
            exists = safe_path.exists()
            return ToolResult(True, f"Path exists: {exists}", data={"exists": exists, "is_file": safe_path.is_file(), "is_dir": safe_path.is_dir()})

        if action == "delete_file" or action == "delete":
            if not safe_path.exists():
                return ToolResult(False, f"Cannot delete: file '{path_str}' does not exist", error_code="FILE_NOT_FOUND")
            try:
                if safe_path.is_file():
                    safe_path.unlink()
                    return ToolResult(True, f"Deleted file '{safe_path.name}'")
                return ToolResult(False, f"Cannot delete: '{path_str}' is a directory")
            except Exception as exc:
                return ToolResult(False, f"Failed to delete file: {exc}")

        return ToolResult(False, f"Unsupported filesystem action '{action}'")
