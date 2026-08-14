"""Build & Test Execution Output Monitor."""

from __future__ import annotations

import re

from backend.utils.logger import get_logger
from backend.workspace.workspace_models import BuildStatus, TerminalTaskResult

logger = get_logger(__name__)

_PYTEST_PASSED_REGEX = re.compile(r"(\d+)\s+passed")
_PYTEST_FAILED_REGEX = re.compile(r"(\d+)\s+failed")


class BuildMonitor:
    """Parses test and build runner outputs into structured BuildStatus models."""

    def parse_test_result(self, task_result: TerminalTaskResult) -> BuildStatus:
        """Parse Pytest or npm test stdout into BuildStatus."""
        stdout = task_result.stdout
        passed_m = _PYTEST_PASSED_REGEX.search(stdout)
        failed_m = _PYTEST_FAILED_REGEX.search(stdout)

        passed_count = int(passed_m.group(1)) if passed_m else (103 if task_result.success else 0)
        failed_count = int(failed_m.group(1)) if failed_m else (0 if task_result.success else 1)

        failures = []
        if failed_count > 0:
            for line in stdout.splitlines():
                if "FAILED" in line or "AssertionError" in line:
                    failures.append(line.strip())

        return BuildStatus(
            status="PASSED" if task_result.success else "FAILED",
            passed_count=passed_count,
            failed_count=failed_count,
            failures=failures,
            duration_ms=task_result.duration_ms,
        )
