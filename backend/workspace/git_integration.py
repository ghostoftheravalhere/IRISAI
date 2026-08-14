"""Git Subprocess Integration Service."""

from __future__ import annotations

import subprocess
from typing import Sequence

from backend.utils.logger import get_logger
from backend.workspace.workspace_models import GitStatus

logger = get_logger(__name__)


class GitIntegration:
    """Provides local Git repository status, branch info, and recent commits."""

    def __init__(self, cwd: str = ".") -> None:
        self._cwd = cwd

    def _run_git(self, args: Sequence[str]) -> str:
        try:
            completed = subprocess.run(
                ["git"] + list(args),
                cwd=self._cwd,
                capture_output=True,
                text=True,
                check=False,
            )
            return (completed.stdout or "").strip()
        except Exception:
            return ""

    def get_status(self) -> GitStatus:
        """Inspect local Git status and return GitStatus model."""
        branch = self._run_git(["branch", "--show-current"]) or "main"
        status_output = self._run_git(["status", "--porcelain"])

        modified = []
        untracked = []
        for line in status_output.splitlines():
            line = line.strip()
            if line.startswith("M "):
                modified.append(line[2:].strip())
            elif line.startswith("??"):
                untracked.append(line[2:].strip())

        log_output = self._run_git(["log", "-n", "5", "--oneline"])
        commits = [c.strip() for c in log_output.splitlines() if c.strip()]

        return GitStatus(
            branch=branch,
            clean=len(modified) == 0 and len(untracked) == 0,
            modified_files=modified,
            untracked_files=untracked,
            recent_commits=commits,
        )
