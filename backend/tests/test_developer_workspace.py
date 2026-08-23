"""Unit tests for Developer Workspace & Environment Intelligence Subsystem."""

from __future__ import annotations

from pathlib import Path

from backend.brain.skills.base import SkillExecutionContext
from backend.brain.skills.developer_skill import DeveloperWorkspaceSkill
from backend.workspace.build_monitor import BuildMonitor
from backend.workspace.git_integration import GitIntegration
from backend.workspace.project_detector import ProjectDetector
from backend.workspace.terminal_runner import TerminalTaskRunner, TerminalTaskResult
from backend.workspace.workspace_manager import WorkspaceManager


def test_project_detector():
    detector = ProjectDetector()
    profile = detector.detect_project(Path.cwd())

    assert profile.name is not None
    assert profile.project_type in ("python", "node", "hybrid", "generic")
    assert profile.has_git is True


def test_git_integration():
    git = GitIntegration(cwd=str(Path.cwd()))
    status = git.get_status()

    assert status.branch is not None
    assert isinstance(status.clean, bool)


def test_terminal_runner_and_build_monitor():
    runner = TerminalTaskRunner()
    res = runner.run_command("python -c \"print('test passed')\"")

    assert res.success is True
    assert "test passed" in res.stdout

    monitor = BuildMonitor()
    status = monitor.parse_test_result(res)
    assert status.status == "PASSED"


def test_workspace_manager_and_developer_skill():
    manager = WorkspaceManager(workspace_root=Path.cwd())
    profile = manager.get_active_profile()
    assert profile.name is not None

    skill = DeveloperWorkspaceSkill(workspace_manager=manager)
    assert skill.can_handle("RUN_TESTS") is True
    assert skill.can_handle("GIT_STATUS") is True

    git_res = skill.execute(SkillExecutionContext(intent="GIT_STATUS"))
    assert git_res.success is True
    assert "Git branch" in git_res.message
