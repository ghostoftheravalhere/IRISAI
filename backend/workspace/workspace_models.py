"""Developer Workspace & Environment Intelligence Data Models."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any
import uuid


@dataclass
class ProjectProfile:
    """Model representing an active developer project workspace."""

    name: str
    root_path: str
    project_type: str  # "python", "node", "hybrid"
    git_branch: str = "main"
    has_git: bool = True
    test_runner: str = "pytest"
    dev_server_command: str = "npm run dev"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TerminalTaskResult:
    """Outcome of a developer terminal task execution."""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    success: bool
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class BuildStatus:
    """Structured build or test run status model."""

    status: str  # "PASSED", "FAILED", "RUNNING"
    passed_count: int = 0
    failed_count: int = 0
    failures: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class GitStatus:
    """Model representing Git repository status."""

    branch: str
    clean: bool
    modified_files: list[str] = field(default_factory=list)
    untracked_files: list[str] = field(default_factory=list)
    recent_commits: list[str] = field(default_factory=list)
