"""WebSearchTool providing public web search capabilities."""

from __future__ import annotations

from typing import Any

from backend.agent.policy_engine import PermissionLevel
from backend.agent.task_state import TaskState
from backend.agent.tool_registry import ToolDescriptor, ToolResult
from backend.brain.skills.browser_skill import BrowserSkill
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class WebSearchTool:
    """Agent Tool wrapping web search queries."""

    def __init__(self, browser_skill: BrowserSkill | None = None) -> None:
        self._browser_skill = browser_skill or BrowserSkill()

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            tool_id="web_search_tool",
            name="web_search_tool",
            description="Performs public web search queries for people, documentation, news, or general information.",
            permission_level=PermissionLevel.SAFE,
            input_schema={"query": "Search query string"},
            output_schema={"success": "bool", "message": "str", "data": "dict"},
        )

    def execute(self, params: dict[str, Any], task_state: TaskState | None = None) -> ToolResult:
        """Execute public web search query."""
        query = str(params.get("query") or params.get("target") or "").strip()
        if not query:
            return ToolResult(False, "Search query missing")

        logger.info("WebSearchTool executing query: '%s'", query)
        from backend.brain.skills.base import SkillExecutionContext
        ctx = SkillExecutionContext(intent="BROWSER_SEARCH", params={"query": query})
        res = self._browser_skill.execute(ctx)
        if res.success:
            return ToolResult(
                True,
                f"Web search executed for '{query}'",
                data={"query": query, "url": res.result_data.get("url"), "snippet": f"SearchResults for {query}"},
            )
        return ToolResult(False, f"Web search failed for query '{query}': {res.message}")
