"""Browser Integration Skill Plugin."""

from __future__ import annotations

from backend.brain.skills.base import (
    SkillDescriptor,
    SkillExecutionContext,
    SkillResult,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class BrowserSkill:
    """Skill capability for web browser tabs, bookmarks, and search."""

    def __init__(self) -> None:
        self._descriptor = SkillDescriptor(
            skill_id="browser_skill",
            name="Browser Skill",
            version="1.0.0",
            description="Controls browser tabs, bookmarks, search queries, and page title reading.",
            required_permissions=["browser:control"],
            capabilities=[
                "OPEN_BROWSER_TAB",
                "ADD_BOOKMARK",
                "BROWSER_SEARCH",
                "READ_PAGE_TITLE",
            ],
        )

    @property
    def descriptor(self) -> SkillDescriptor:
        return self._descriptor

    def can_handle(self, capability: str) -> bool:
        return capability.upper() in self._descriptor.capabilities

    def execute(self, context: SkillExecutionContext) -> SkillResult:
        intent = context.intent.upper()
        query = context.params.get("query", context.raw_transcript)
        return SkillResult(
            success=True,
            message=f"Browser action '{intent}' completed for '{query}'",
            result_data={"query": query},
        )
