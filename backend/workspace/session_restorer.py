"""Developer Session Restorer Service."""

from __future__ import annotations

from backend.utils.logger import get_logger
from backend.workspace.workspace_models import ProjectProfile

logger = get_logger(__name__)


class SessionRestorer:
    """Restores developer project session state and active workspace profile."""

    def restore_session(self, profile: ProjectProfile) -> dict:
        """Restore active developer workspace session."""
        logger.info("Restored developer workspace session for project: %s", profile.name)
        return {
            "status": "RESTORED",
            "project_name": profile.name,
            "root_path": profile.root_path,
            "git_branch": profile.git_branch,
        }
