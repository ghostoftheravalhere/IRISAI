"""Central Developer Workspace Manager Subsystem."""

from __future__ import annotations

from pathlib import Path
from threading import RLock

from backend.core.events.bus import EventBus
from backend.utils.logger import get_logger
from backend.workspace.build_monitor import BuildMonitor
from backend.workspace.git_integration import GitIntegration
from backend.workspace.project_detector import ProjectDetector
from backend.workspace.session_restorer import SessionRestorer
from backend.workspace.terminal_runner import TerminalTaskRunner
from backend.workspace.workspace_models import BuildStatus, GitStatus, ProjectProfile, TerminalTaskResult

logger = get_logger(__name__)


class WorkspaceManager:
    """Central Developer Workspace Subsystem Coordinator."""

    def __init__(
        self,
        event_bus: EventBus | None = None,
        workspace_root: str | Path | None = None,
        enabled: bool = True,
    ) -> None:
        self._event_bus = event_bus
        self._root = Path(workspace_root) if workspace_root else Path.cwd()
        self._detector = ProjectDetector()
        self._git = GitIntegration(cwd=str(self._root))
        self._runner = TerminalTaskRunner(default_cwd=str(self._root))
        self._monitor = BuildMonitor()
        self._restorer = SessionRestorer()
        self._active_profile: ProjectProfile | None = None
        self._enabled = enabled
        self._lock = RLock()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def get_active_profile(self) -> ProjectProfile:
        """Return or detect active developer project profile."""
        with self._lock:
            if self._active_profile is None:
                self._active_profile = self._detector.detect_project(self._root)
            return self._active_profile

    def get_git_status(self) -> GitStatus:
        """Inspect Git repository status."""
        with self._lock:
            return self._git.get_status()

    def run_tests(self) -> tuple[TerminalTaskResult, BuildStatus]:
        """Execute project test suite and return TerminalTaskResult & BuildStatus."""
        with self._lock:
            profile = self.get_active_profile()
            cmd = "backend\\.venv\\Scripts\\python.exe -m pytest" if profile.project_type in ("python", "hybrid") else "npm test"
            res = self._runner.run_command(cmd)
            status = self._monitor.parse_test_result(res)
            return res, status

    def restore_last_session(self) -> dict:
        """Restore active developer session."""
        with self._lock:
            profile = self.get_active_profile()
            return self._restorer.restore_session(profile)
