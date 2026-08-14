"""Async Terminal Task Runner Service."""

from __future__ import annotations

import subprocess
import time

from backend.utils.logger import get_logger
from backend.workspace.workspace_models import TerminalTaskResult

logger = get_logger(__name__)


class TerminalTaskRunner:
    """Executes developer terminal commands with timeouts and output capture."""

    def __init__(self, default_cwd: str = ".") -> None:
        self._default_cwd = default_cwd

    def run_command(self, command: str, cwd: str | None = None, timeout_sec: float = 60.0) -> TerminalTaskResult:
        """Execute a shell command synchronously and capture results."""
        t0 = time.time()
        work_dir = cwd or self._default_cwd

        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
            duration_ms = (time.time() - t0) * 1000.0
            return TerminalTaskResult(
                command=command,
                exit_code=completed.returncode,
                stdout=(completed.stdout or "").strip(),
                stderr=(completed.stderr or "").strip(),
                duration_ms=duration_ms,
                success=completed.returncode == 0,
            )
        except subprocess.TimeoutExpired:
            duration_ms = (time.time() - t0) * 1000.0
            return TerminalTaskResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {timeout_sec}s",
                duration_ms=duration_ms,
                success=False,
            )
        except Exception as e:
            duration_ms = (time.time() - t0) * 1000.0
            return TerminalTaskResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
                success=False,
            )
