"""FastAPI Router for Developer Workspace Subsystem."""

from __future__ import annotations

from fastapi import APIRouter

from backend.workspace.workspace_manager import WorkspaceManager

router = APIRouter(prefix="/workspace", tags=["workspace"])

# Shared WorkspaceManager singleton instance
_workspace_manager = WorkspaceManager()


@router.get("/project")
def get_active_project():
    """Return current active developer project profile."""
    profile = _workspace_manager.get_active_profile()
    return {
        "name": profile.name,
        "root_path": profile.root_path,
        "project_type": profile.project_type,
        "git_branch": profile.git_branch,
        "test_runner": profile.test_runner,
    }


@router.get("/git-status")
def get_git_status():
    """Get Git status, current branch, and recent commits."""
    status = _workspace_manager.get_git_status()
    return {
        "branch": status.branch,
        "clean": status.clean,
        "modified_files": status.modified_files,
        "recent_commits": status.recent_commits,
    }


@router.post("/run-tests")
def run_tests():
    """Trigger developer test suite run."""
    res, status = _workspace_manager.run_tests()
    return {
        "success": res.success,
        "status": status.status,
        "passed_count": status.passed_count,
        "failed_count": status.failed_count,
        "duration_ms": status.duration_ms,
    }


@router.post("/restore")
def restore_session():
    """Restore active developer session state."""
    return _workspace_manager.restore_last_session()
