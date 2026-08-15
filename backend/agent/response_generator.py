"""ResponseGenerator synthesizing plan step outcomes into natural, concise conversational language."""

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
            return f"I ran into an issue while working on your request: {task_state.error_message or 'Operation cancelled or failed'}"

        if not task_state.history:
            return f"I completed your request for '{task_state.user_goal}'."

        last_step, last_res = task_state.history[-1]

        if isinstance(last_res, ToolResult) and last_res.data:
            data = last_res.data

            # 1. Project Summary / Git status
            if "recent_commits" in data or "commits" in data:
                commits = data.get("recent_commits") or data.get("commits") or []
                commits_str = "; ".join(commits[:3]) if commits else "No recent commits"
                branch = data.get("branch", "main")
                mod_cnt = data.get("modified_count", data.get("has_changes", 0))
                return f"Sir, we're on branch '{branch}'. Modified files: {mod_cnt}. Recent work: {commits_str}."

            # 2. Filesystem Candidates & Search
            if "candidates" in data and data["candidates"]:
                cands = data["candidates"]
                if len(cands) == 1:
                    return f"I found the matching file '{cands[0]['name']}' at '{cands[0]['path']}'."
                c_list_str = ", ".join([f"{c['index']}. {c['name']}" for c in cands[:3]])
                return f"I found {len(cands)} matching files: {c_list_str}. Which one would you like me to open?"

            if "content" in data:
                summary_snippet = str(data["content"])[:250].replace("\n", " ").strip()
                return f"I read the document. Summary: {summary_snippet}..."

            # 3. Web Search & Person Search
            if "sources" in data:
                query = data.get("query", "search")
                is_person = data.get("is_person_search", False)
                sources = data.get("sources", [])
                src_url = sources[0].get("url", "") if sources else ""
                if is_person:
                    return f"I found a possible match for '{query}' online. Source: {src_url}."
                return f"I searched online for '{query}' and retrieved the documentation. Source: {src_url}."

            if "entries" in data:
                return f"I checked the workspace directory and found {len(data['entries'])} items."

            if "matches" in data and "query" not in data:
                matches = data["matches"]
                return f"I found {len(matches)} files: {', '.join(matches[:3])}."

            # 4. Email Tool Responses
            if "unread_count" in data:
                cnt = data["unread_count"]
                return f"Yes, sir. You have {cnt} unread emails."

            if "pending_messages" in data:
                p_cnt = len(data["pending_messages"])
                return f"I found {p_cnt} pending messages requiring your attention."

            # 5. Calendar Tool Responses
            if "next_event" in data:
                ne = data["next_event"]
                return f"Your next event is '{ne.get('title')}' at {ne.get('time')} ({ne.get('starts_in', 'today')})."

            if "events" in data and not "candidates" in data:
                evts = data["events"]
                count = len(evts)
                date_str = data.get("date", "scheduled")
                if count == 0:
                    return f"You have no events scheduled for {date_str}."
                titles = ", ".join([e.get("title", "") for e in evts[:2]])
                return f"You have {count} event(s) scheduled for {date_str}: {titles}."

            # 6. GitHub Tool Responses
            if "activity_summary" in data:
                acc = data["activity_summary"]
                return f"GitHub repo '{acc.get('repo')}': {acc.get('recent_commits_count', 0)} recent commits, {acc.get('open_issues', 0)} open issue(s), CI {acc.get('ci_status', 'passing')}."

            if "workflow_status" in data:
                ws = data["workflow_status"]
                return f"The latest GitHub Actions workflow for '{ws.get('repo')}' finished with status '{ws.get('conclusion', ws.get('status'))}'."

        if isinstance(last_res, ToolResult):
            return f"Completed: {last_res.message}"

        return f"I have finished executing your request for '{task_state.user_goal}'."

    @staticmethod
    def generate_confirmation_prompt(tool_name: str, params: dict[str, Any], reason: str) -> str:
        """Format user confirmation prompt for PolicyEngine interception."""
        return f"I am about to execute '{tool_name}' ({params}). {reason}. Do you want me to proceed? (Yes/No)"
