"""GitTool providing read-only git repository status, branch inspection, commit logs, and project summary queries."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Any

from backend.agent.policy_engine import PermissionLevel
from backend.agent.task_state import TaskState
from backend.agent.tool_registry import ToolDescriptor, ToolResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GitTool:
    """Read-Only Git Repository Tool for IRIS AI."""

    def __init__(self, cwd: str | None = None) -> None:
        self._cwd = cwd or os.getcwd()

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            tool_id="git_tool",
            name="git_tool",
            description="Reads git repository status, branch info, commit logs, diff summaries, and project completion state safely.",
            permission_level=PermissionLevel.SAFE,
            input_schema={
                "action": "get_status | get_log | get_branch | get_diff | project_summary",
                "count": "Number of recent commits to fetch (default 5)",
                "since": "Time filter (e.g. '1.day.ago' or 'yesterday')",
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

        if action in ("get_status", "status", "git_status"):
            ok, out = self._run_git_cmd(["status", "--short"])
            if not ok:
                return ToolResult(False, f"Git status failed: {out}", error_code="GIT_EXECUTION_FAILED")
            ok_b, branch = self._run_git_cmd(["branch", "--show-current"])
            files_modified = [line.strip() for line in out.splitlines() if line.strip()]
            return ToolResult(
                True,
                f"Branch: '{branch or 'main'}', Modified files: {len(files_modified)}",
                data={
                    "branch": branch or "main",
                    "status_summary": out,
                    "modified_files": files_modified,
                    "has_changes": bool(files_modified),
                },
            )

        if action in ("get_log", "log", "git_log"):
            count = int(params.get("count") or 5)
            since = params.get("since")
            git_args = ["log", f"-n{count}", "--oneline"]
            if since:
                git_args.append(f"--since={since}")

            ok, out = self._run_git_cmd(git_args)
            if not ok:
                return ToolResult(False, f"Git log failed: {out}", error_code="GIT_EXECUTION_FAILED")
            commits = [line.strip() for line in out.splitlines() if line.strip()]
            return ToolResult(True, f"Retrieved {len(commits)} recent commits", data={"commits": commits, "count": len(commits)})

        if action in ("get_branch", "branch", "git_branch"):
            ok, branch = self._run_git_cmd(["branch", "--show-current"])
            return ToolResult(ok, f"Active branch: '{branch}'", data={"branch": branch or "main"})

        if action in ("get_diff", "diff", "git_diff"):
            ok, out = self._run_git_cmd(["diff", "--stat"])
            return ToolResult(ok, f"Git diff summary retrieved", data={"diff_summary": out or "No uncommitted diffs"})

        if action in ("project_summary", "get_project_summary"):
            ok_b, branch = self._run_git_cmd(["branch", "--show-current"])
            ok_s, status_out = self._run_git_cmd(["status", "--short"])
            ok_l, log_out = self._run_git_cmd(["log", "-n5", "--oneline"])
            commits = [l.strip() for l in log_out.splitlines() if l.strip()] if ok_l else []
            modified_count = len([l for l in status_out.splitlines() if l.strip()]) if ok_s else 0

            # Supporting context from .ai/current_state.md or walkthrough.md if present
            doc_context = ""
            for doc_name in (".ai/current_state.md", "walkthrough.md", "README.md"):
                doc_p = Path(self._cwd) / doc_name
                if doc_p.is_file():
                    try:
                        doc_context = doc_p.read_text(encoding="utf-8", errors="replace")[:1500]
                        break
                    except Exception:
                        pass

            summary_msg = f"Branch: '{branch or 'main'}', Modified files: {modified_count}, Recent commits: {len(commits)}"
            return ToolResult(
                True,
                summary_msg,
                data={
                    "branch": branch or "main",
                    "modified_count": modified_count,
                    "recent_commits": commits,
                    "doc_context": doc_context,
                },
            )

        return ToolResult(False, f"Unsupported git action '{action}'")
