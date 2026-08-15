"""GitTool providing read-only git repository status, branch inspection, and commit log queries."""

from __future__ import annotations

import os
import subprocess
from typing import Any

from backend.agent.policy_engine import PermissionLevel
from backend.agent.task_state import TaskState
from backend.agent.tool_registry import ToolDescriptor, ToolResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GitTool:
    """Read-Only Git Repository Tool."""

    def __init__(self, cwd: str | None = None) -> None:
        self._cwd = cwd or os.getcwd()

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            tool_id="git_tool",
            name="git_tool",
            description="Reads git repository status, branch info, commit logs, and diff summaries safely.",
            permission_level=PermissionLevel.SAFE,
            input_schema={
                "action": "get_status | get_log | get_branch",
                "count": "Number of recent commits to fetch (default 5)",
            },
            output_schema={"success": "bool", "message": "str", "data": "dict"},
        )

    def _run_git_cmd(self, args: list[str]) -> tuple[bool, str]:
        """Run read-only git command safely."""
        try:
            cmd = ["git"] + args
            res = subprocess.run(cmd, cwd=self._cwd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                return True, res.stdout.strip()
            return False, res.stderr.strip() or res.stdout.strip()
        except Exception as exc:
            return False, str(exc)

    def execute(self, params: dict[str, Any], task_state: TaskState | None = None) -> ToolResult:
        """Execute git read-only action."""
        action = str(params.get("action") or "get_status").lower().strip()

        if action == "get_status" or action == "status":
            ok, out = self._run_git_cmd(["status", "--short"])
            if not ok:
                return ToolResult(False, f"Git status failed: {out}")
            ok_b, branch = self._run_git_cmd(["branch", "--show-current"])
            return ToolResult(
                True,
                f"Branch: '{branch or 'main'}', Modified files: {len(out.splitlines()) if out else 0}",
                data={"branch": branch, "status_summary": out, "has_changes": bool(out)},
            )

        if action == "get_log" or action == "log":
            count = int(params.get("count") or 5)
            ok, out = self._run_git_cmd(["log", f"-n{count}", "--oneline"])
            if not ok:
                return ToolResult(False, f"Git log failed: {out}")
            commits = [line.strip() for line in out.splitlines() if line.strip()]
            return ToolResult(True, f"Retrieved {len(commits)} recent commits", data={"commits": commits})

        if action == "get_branch" or action == "branch":
            ok, branch = self._run_git_cmd(["branch", "--show-current"])
            return ToolResult(ok, f"Active branch: '{branch}'", data={"branch": branch})

        return ToolResult(False, f"Unsupported git action '{action}'")
