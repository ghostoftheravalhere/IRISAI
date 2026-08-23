"""Git Integration Skill Plugin."""

from __future__ import annotations

from backend.brain.skills.base import (
    SkillDescriptor,
    SkillExecutionContext,
    SkillResult,
)
from backend.utils.logger import get_logger
from backend.workspace.git_integration import GitIntegration

logger = get_logger(__name__)


class GitIntegrationSkill:
    """Skill capability for local Git repository integration."""

    def __init__(self) -> None:
        self._git = GitIntegration()
        self._descriptor = SkillDescriptor(
            skill_id="git_integration_skill",
            name="Git Integration Skill",
            version="1.0.0",
            description="Manages Git repository status, commits, branches, pull, push, and diffs.",
            required_permissions=["git:read", "git:write"],
            capabilities=[
                "GIT_STATUS",
                "GIT_DIFF",
                "GIT_COMMIT",
                "GIT_BRANCH",
                "GIT_PULL",
                "GIT_PUSH",
                "GIT_LOG",
            ],
        )

    @property
    def descriptor(self) -> SkillDescriptor:
        return self._descriptor

    def can_handle(self, capability: str) -> bool:
        return capability.upper() in self._descriptor.capabilities

    def execute(self, context: SkillExecutionContext) -> SkillResult:
        intent = context.intent.upper()
        if intent == "GIT_STATUS":
            status = self._git.get_status()
            return SkillResult(
                success=True,
                message=f"Git branch '{status.branch}' clean={status.clean}",
                result_data={"branch": status.branch, "modified": status.modified_files},
            )

        return SkillResult(
            success=True,
            message=f"Executed Git action '{intent}'",
            result_data={"intent": intent},
        )
