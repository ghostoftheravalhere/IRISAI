"""ResponseGenerator synthesizing plan step outcomes into natural conversational language."""

from __future__ import annotations

from typing import Any

from backend.agent.task_state import PlanStep, TaskState
from backend.agent.tool_registry import ToolResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ResponseGenerator:
    """Formats raw tool execution results into user-facing conversational natural language responses."""

    @staticmethod
    def generate_final_response(task_state: TaskState) -> str:
        """Synthesize final response for completed or failed TaskState."""
        if task_state.status == "FAILED" or task_state.error_message:
            return f"I ran into an issue while working on your request: {task_state.error_message or 'Unknown error'}"

        if not task_state.history:
            return f"I completed your request for '{task_state.user_goal}'."

        last_step, last_res = task_state.history[-1]

        # Check specific tool outcome data for tailored response
        if isinstance(last_res, ToolResult) and last_res.data:
            data = last_res.data
            if "commits" in data:
                commits_str = "; ".join(data["commits"][:3])
                return f"I checked your repository on branch '{data.get('branch', 'main')}'. Recent completions: {commits_str}."
            if "content" in data:
                summary_snippet = str(data["content"])[:250].replace("\n", " ").strip()
                return f"I read the document. Summary: {summary_snippet}..."
            if "entries" in data:
                return f"I checked the workspace directory and found {len(data['entries'])} items."
            if "matches" in data:
                return f"I found {len(data['matches'])} files: {', '.join(data['matches'][:3])}."
            if "query" in data:
                return f"I searched online for '{data['query']}' and retrieved the latest results."

        if isinstance(last_res, ToolResult):
            return f"Completed: {last_res.message}"

        return f"I have finished executing your request for '{task_state.user_goal}'."

    @staticmethod
    def generate_confirmation_prompt(tool_name: str, params: dict[str, Any], reason: str) -> str:
        """Format user confirmation prompt for PolicyEngine interception."""
        return f"I am about to execute '{tool_name}' ({params}). {reason}. Do you want me to proceed? (Yes/No)"
