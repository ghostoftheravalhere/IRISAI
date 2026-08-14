"""Project Detector Service."""

from __future__ import annotations

from pathlib import Path

from backend.utils.logger import get_logger
from backend.workspace.workspace_models import ProjectProfile

logger = get_logger(__name__)


class ProjectDetector:
    """Detects active project type, root path, and dev tool configuration."""

    def detect_project(self, root_dir: str | Path) -> ProjectProfile:
        """Inspect a directory and return a structured ProjectProfile."""
        path = Path(root_dir)
        name = path.name or "IRISAI"

        has_python = (path / "pyproject.toml").exists() or (path / "pytest.ini").exists() or (path / "backend").exists()
        has_node = (path / "package.json").exists() or (path / "frontend").exists()
        has_git = (path / ".git").exists() or (path.parent / ".git").exists()

        if has_python and has_node:
            proj_type = "hybrid"
        elif has_python:
            proj_type = "python"
        elif has_node:
            proj_type = "node"
        else:
            proj_type = "generic"

        return ProjectProfile(
            name=name,
            root_path=str(path.resolve()),
            project_type=proj_type,
            git_branch="main",
            has_git=has_git,
            test_runner="pytest" if has_python else "npm test",
            dev_server_command="npm run dev" if has_node else "python main.py",
        )
