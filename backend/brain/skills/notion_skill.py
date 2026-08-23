"""Notion Notes Integration Skill Plugin."""

from __future__ import annotations

from backend.brain.skills.base import (
    SkillDescriptor,
    SkillExecutionContext,
    SkillResult,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class NotionSkill:
    """Skill capability for Notion notes, pages, and daily workspace notes."""

    def __init__(self) -> None:
        self._descriptor = SkillDescriptor(
            skill_id="notion_skill",
            name="Notion Skill",
            version="1.0.0",
            description="Manages Notion pages, daily notes, and workspace search.",
            required_permissions=["notion:read", "notion:write"],
            capabilities=[
                "OPEN_NOTION_PAGE",
                "OPEN_DAILY_NOTES",
                "SEARCH_NOTION_NOTES",
            ],
        )

    @property
    def descriptor(self) -> SkillDescriptor:
        return self._descriptor

    def can_handle(self, capability: str) -> bool:
        return capability.upper() in self._descriptor.capabilities

    def execute(self, context: SkillExecutionContext) -> SkillResult:
        intent = context.intent.upper()
        query = context.params.get("query", "Daily Notes")
        return SkillResult(
            success=True,
            message=f"Notion action '{intent}' executed for '{query}'",
            result_data={"query": query},
        )
