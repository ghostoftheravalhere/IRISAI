"""Planner decomposing user goals into executable PlanStep sequences and reasoning over tool feedback."""

from __future__ import annotations

import re
from typing import Any

from backend.agent.task_state import Plan, PlanStep, TaskState
from backend.agent.tool_registry import ToolDescriptor, ToolResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class Planner:
    """Decomposes user goals into structured multi-step plans and evaluates step result feedback."""

    def __init__(self) -> None:
        pass

    def plan(self, intent: Any = None) -> Any:
        """Backward compatibility pass-through for legacy container contract."""
        return intent

    def create_plan(self, goal: str, available_tools: list[ToolDescriptor], context: dict[str, Any] | None = None) -> Plan:
        """Decompose user goal into executable Plan."""
        goal_lower = re.sub(r"^iris,?\s*", "", goal.lower().strip(), flags=re.IGNORECASE).strip()
        steps: list[PlanStep] = []

        # 1. GitHub repo progress query
        if "github" in goal_lower or "repository" in goal_lower or "completed" in goal_lower or "git status" in goal_lower:
            steps.append(PlanStep(1, "git_tool", "Check git repository status and branch", {"action": "get_status"}))
            steps.append(PlanStep(2, "git_tool", "Fetch recent commit history", {"action": "get_log", "count": 5}))
            steps.append(PlanStep(3, "filesystem_tool", "Read repository progress summary", {"action": "read_file", "path": ".ai/current_state.md"}))
            return Plan(goal=goal, steps=steps)

        # 2. Compound actions ("Open Notepad and type hello" or "Open VS Code and tell me which files changed")
        compound_match = re.search(r"open\s+([\w\s]+?)\s+and\s+(type|write|tell|check|show)\s+(.+)", goal_lower)
        if compound_match:
            app_name = compound_match.group(1).strip()
            action_type = compound_match.group(2).strip()
            payload = compound_match.group(3).strip()

            steps.append(PlanStep(1, "desktop_tool", f"Open application '{app_name}'", {"action": "open_application", "target": app_name}))
            if action_type in ("type", "write"):
                steps.append(PlanStep(2, "desktop_tool", f"Type text '{payload}'", {"action": "type_text", "text": payload}))
            elif "files" in payload or "changed" in payload or "git" in payload:
                steps.append(PlanStep(2, "git_tool", "Check git status for modified files", {"action": "get_status"}))
            else:
                steps.append(PlanStep(2, "desktop_tool", f"Execute action '{action_type} {payload}'", {"action": "type_text", "text": payload}))
            return Plan(goal=goal, steps=steps)

        # 2. Delete file request (Confirmation Required)
        if "delete file" in goal_lower or "remove file" in goal_lower or "delete " in goal_lower:
            file_match = re.search(r"(file|named)\s+['\"]?([\w\.\-/]+)['\"]?", goal_lower)
            target_path = file_match.group(2) if file_match else goal_lower.replace("delete file", "").replace("delete", "").strip()
            steps.append(PlanStep(1, "filesystem_tool", f"Delete file '{target_path}'", {"action": "delete_file", "path": target_path}))
            return Plan(goal=goal, steps=steps)

        # 4. Web search query (e.g. "search the web for Python 3.14 release information")
        if "search" in goal_lower or "find info" in goal_lower or "who is" in goal_lower:
            query = re.sub(r"^(search for|search online for|search the web for|search|find|who is)\s+", "", goal_lower, flags=re.IGNORECASE).strip()
            query = re.sub(r"\s+and\s+summarize.*$", "", query, flags=re.IGNORECASE).strip()
            steps.append(PlanStep(1, "web_search_tool", f"Search web for '{query}'", {"query": query}))
            return Plan(goal=goal, steps=steps)

        # 5. Read and summarize document query
        if "read" in goal_lower or "summarize" in goal_lower:
            path_match = re.search(r"(file|document|report|path)\s+['\"]?([\w\.\-/]+)['\"]?", goal_lower)
            target_path = path_match.group(2) if path_match else ".ai/current_state.md"
            steps.append(PlanStep(1, "filesystem_tool", f"Read text document '{target_path}'", {"action": "read_file", "path": target_path}))
            return Plan(goal=goal, steps=steps)

        # 6. Open project and continue where stopped
        if "open my project" in goal_lower or "open project" in goal_lower or "continue" in goal_lower:
            steps.append(PlanStep(1, "desktop_tool", "Open VS Code application", {"action": "open_application", "target": "vscode"}))
            steps.append(PlanStep(2, "filesystem_tool", "Read project state", {"action": "read_file", "path": ".ai/current_state.md"}))
            return Plan(goal=goal, steps=steps)

        # 7. Find file query (e.g., "find my project report")
        if "find" in goal_lower or "locate" in goal_lower:
            filename_match = re.search(r"(file|report|document|named)\s+['\"]?([\w\.\-/]+)['\"]?", goal_lower)
            query = filename_match.group(2) if filename_match else "report"
            steps.append(PlanStep(1, "filesystem_tool", f"Search files matching '{query}'", {"action": "search_files", "query": query}))
            return Plan(goal=goal, steps=steps)

        # 8. Default single-step desktop UI action
        steps.append(PlanStep(1, "desktop_tool", f"Execute command '{goal}'", {"action": "open_application", "target": goal}))
        return Plan(goal=goal, steps=steps)

    def evaluate_step_result(
        self,
        step: PlanStep,
        result: ToolResult,
        task_state: TaskState,
    ) -> str:
        """Inspect tool result feedback and decide plan continuation ('CONTINUE', 'REPLAN', 'STOP_FAILED')."""
        if result.success:
            logger.info("Step %d ('%s') succeeded: %s", step.step_id, step.tool_name, result.message)
            return "CONTINUE"

        logger.warning("Step %d ('%s') failed: %s (code=%s)", step.step_id, step.tool_name, result.message, result.error_code)

        # File not found error recovery attempt
        if result.error_code == "FILE_NOT_FOUND" and step.tool_name == "filesystem_tool":
            logger.info("Attempting dynamic replan: search files instead of direct read")
            # Replace remaining plan with file search
            search_step = PlanStep(step.step_id + 1, "filesystem_tool", "Search files in workspace", {"action": "search_files", "query": "state"})
            if task_state.current_plan:
                task_state.current_plan.steps.append(search_step)
            return "REPLAN"

        if result.error_code == "CONFIRMATION_REQUIRED":
            return "WAITING_CONFIRMATION"

        return "STOP_FAILED"
