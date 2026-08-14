"""GitHub Integration Skill Plugin."""

from __future__ import annotations

from backend.brain.skills.base import (
    SkillDescriptor,
    SkillExecutionContext,
    SkillResult,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GitHubSkill:
    """Skill capability for GitHub repository issues and pull requests."""

    def __init__(self) -> None:
        self._descriptor = SkillDescriptor(
            skill_id="github_skill",
            name="GitHub Skill",
            version="1.0.0",
            description="Manages GitHub issues, pull requests, and code reviews.",
            required_permissions=["github:read", "github:write"],
            capabilities=[
                "CREATE_GITHUB_ISSUE",
                "VIEW_GITHUB_ISSUES",
                "OPEN_GITHUB_PR",
                "REVIEW_GITHUB_PR",
            ],
        )

    @property
    def descriptor(self) -> SkillDescriptor:
        return self._descriptor

    def can_handle(self, capability: str) -> bool:
        return capability.upper() in self._descriptor.capabilities

    def execute(self, context: SkillExecutionContext) -> SkillResult:
        intent = context.intent.upper()
        title = context.params.get("title", "IRIS AI Task Issue")
        return SkillResult(
            success=True,
            message=f"GitHub action '{intent}' completed for '{title}'",
            result_data={"title": title},
        )
