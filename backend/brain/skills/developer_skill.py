"""Developer Workspace Skill Capability Plugin."""

from __future__ import annotations

from typing import Any

from backend.brain.skills.base import (
    SkillDescriptor,
    SkillExecutionContext,
    SkillResult,
)
from backend.utils.logger import get_logger
from backend.workspace.workspace_manager import WorkspaceManager

logger = get_logger(__name__)


class DeveloperWorkspaceSkill:
    """Skill capability for developer environment tasks."""

    def __init__(self, workspace_manager: WorkspaceManager | None = None) -> None:
        self._workspace_manager = workspace_manager or WorkspaceManager()
        self._descriptor = SkillDescriptor(
            skill_id="developer_workspace_skill",
            name="Developer Workspace Skill",
            version="1.0.0",
            description="Executes dev tasks, manages Git repos, and monitors test builds.",
            required_permissions=["workspace:read", "workspace:execute"],
            capabilities=[
                "RUN_TESTS",
                "OPEN_WORKSPACE",
                "GIT_STATUS",
                "GIT_LOG",
                "GET_BUILD_STATUS",
                "RESTORE_WORKSPACE",
            ],
        )

    @property
    def descriptor(self) -> SkillDescriptor:
        return self._descriptor

    def can_handle(self, capability: str) -> bool:
        return capability.upper() in self._descriptor.capabilities

    def execute(self, context: SkillExecutionContext) -> SkillResult:
        intent = context.intent.upper()
        if intent == "RUN_TESTS":
            res, status = self._workspace_manager.run_tests()
            return SkillResult(
                success=res.success,
                message=f"Test run completed: {status.passed_count} passed, {status.failed_count} failed.",
                result_data={"passed": status.passed_count, "failed": status.failed_count},
            )
        if intent == "GIT_STATUS":
            status = self._workspace_manager.get_git_status()
            return SkillResult(
                success=True,
                message=f"Git branch '{status.branch}': clean={status.clean}",
                result_data={"branch": status.branch, "modified": status.modified_files},
            )
        if intent == "RESTORE_WORKSPACE":
            res = self._workspace_manager.restore_last_session()
            return SkillResult(
                success=True,
                message=f"Restored workspace session for '{res.get('project_name')}'",
                result_data=res,
            )

        return SkillResult(success=False, message=f"Unsupported intent: {context.intent}")
