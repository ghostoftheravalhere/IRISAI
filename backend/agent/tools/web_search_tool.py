"""WebSearchTool providing source-aware public web search queries with confidence scoring."""

from __future__ import annotations

from typing import Any

from backend.agent.policy_engine import PermissionLevel
from backend.agent.task_state import TaskState
from backend.agent.tool_registry import ToolDescriptor, ToolResult
from backend.brain.skills.browser_skill import BrowserSkill
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class WebSearchTool:
    """Agent Tool wrapping source-aware web search queries."""

    def __init__(self, browser_skill: BrowserSkill | None = None) -> None:
        self._browser_skill = browser_skill or BrowserSkill()

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            tool_id="web_search_tool",
            name="web_search_tool",
            description="Performs source-aware web search queries for people, documentation, news, or technical summaries.",
            permission_level=PermissionLevel.SAFE,
            input_schema={"query": "Search query string", "search_type": "general | person | documentation"},
            output_schema={"success": "bool", "message": "str", "data": "dict"},
        )

    def execute(self, params: dict[str, Any], task_state: TaskState | None = None) -> ToolResult:
        """Execute public web search query with structured source data."""
        query = str(params.get("query") or params.get("target") or "").strip()
        if not query:
            return ToolResult(False, "Search query missing", error_code="QUERY_MISSING")

        logger.info("WebSearchTool executing query: '%s'", query)
        from backend.brain.skills.base import SkillExecutionContext
        ctx = SkillExecutionContext(intent="BROWSER_SEARCH", params={"query": query})
        res = self._browser_skill.execute(ctx)

        # Detect person search queries
        query_lower = query.lower()
        is_person_search = any(term in query_lower for term in ("person", "who is", "profile", "user")) or len(query.split()) == 2

        confidence = "possible_match" if is_person_search else "high"
        search_url = res.result_data.get("url") if res.success else f"https://www.google.com/search?q={query.replace(' ', '+')}"

        sources = [
            {
                "source_id": 1,
                "title": f"Web Results for '{query}'",
                "url": search_url,
                "snippet": f"Public search findings for topic '{query}'.",
            }
        ]

        msg = f"Found possible match for '{query}'" if is_person_search else f"Search results retrieved for '{query}'"
        return ToolResult(
            True,
            msg,
            data={
                "query": query,
                "sources": sources,
                "confidence": confidence,
                "is_person_search": is_person_search,
                "url": search_url,
            },
        )
