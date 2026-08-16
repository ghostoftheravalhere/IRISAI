import concurrent.futures
import json
import re
from typing import Any

from backend.agent.task_state import Plan, PlanStep, TaskState
from backend.agent.tool_registry import ToolDescriptor, ToolResult
from backend.brain.reasoning.provider import PlannerProvider
from backend.utils.logger import get_logger
from backend.voice.command_parser import IntentParserService, VoiceIntentType

logger = get_logger(__name__)


class PlanValidationError(ValueError):
    """Raised when raw model output fails structured plan schema validation."""
    pass


class PlanValidator:
    """Validates raw JSON plan output against IRIS Plan/PlanStep contracts and Tool descriptors."""

    @staticmethod
    def validate(
        raw_json: str,
        goal: str,
        available_tools: list[ToolDescriptor] | None = None,
    ) -> Plan:
        """Parse and validate raw JSON into a structured Plan."""
        if not raw_json or not isinstance(raw_json, str):
            raise PlanValidationError("Raw response is empty or not a string")

        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as err:
            raise PlanValidationError(f"Invalid JSON format: {err}")

        if not isinstance(data, dict):
            raise PlanValidationError("JSON root must be an object/dict")

        steps_raw = data.get("steps")
        if not steps_raw or not isinstance(steps_raw, list):
            raise PlanValidationError("Plan must contain a non-empty 'steps' list")

        registered_names = {t.name.lower() for t in available_tools} if available_tools else set()

        steps: list[PlanStep] = []
        for idx, step_dict in enumerate(steps_raw, start=1):
            if not isinstance(step_dict, dict):
                raise PlanValidationError(f"Step {idx} is not an object/dict")

            tool_name = str(step_dict.get("tool_name") or step_dict.get("tool") or step_dict.get("intent") or "").strip()
            if not tool_name:
                raise PlanValidationError(f"Step {idx} missing 'tool_name' or 'tool'")

            if registered_names and tool_name.lower() not in registered_names:
                raise PlanValidationError(f"Step {idx} references unregistered tool '{tool_name}'")

            desc = str(step_dict.get("description") or f"Step {idx}: {tool_name}")
            params = step_dict.get("params") or step_dict.get("arguments") or {}
            if not isinstance(params, dict):
                params = {"target": str(params)}

            step_id = int(step_dict.get("step_id") or idx)
            steps.append(PlanStep(step_id=step_id, tool_name=tool_name, description=desc, params=params))

        plan_goal = str(data.get("goal") or goal)
        return Plan(goal=plan_goal, steps=steps)


class Planner:
    """Decomposes user goals into structured multi-step plans via neural models or deterministic heuristics."""

    def __init__(
        self,
        provider: PlannerProvider | None = None,
        timeout_seconds: float = 3.0,
        enable_fallback: bool = True,
    ) -> None:
        self._provider = provider
        self._timeout_seconds = timeout_seconds
        self._enable_fallback = enable_fallback
        self._intent_parser = IntentParserService()

    @property
    def provider(self) -> PlannerProvider | None:
        """Return the active planner provider instance."""
        return self._provider

    def plan(self, intent: Any = None) -> Any:
        """Backward compatibility pass-through for legacy container contract."""
        if hasattr(intent, "name") and hasattr(intent, "payload"):
            from backend.core.contracts.action import ActionRequest, ActionType
            from dataclasses import dataclass

            @dataclass
            class LegacyPlan:
                actions: list[Any]

            return LegacyPlan(
                actions=[
                    ActionRequest(
                        action_type=ActionType.NO_ACTION,
                        name=getattr(intent, "name", "UNKNOWN"),
                        payload=getattr(intent, "payload", {}),
                    )
                ]
            )
        return intent

    def create_plan(
        self,
        goal: str,
        available_tools: list[ToolDescriptor],
        context: dict[str, Any] | None = None,
    ) -> Plan:
        """Decompose user goal into executable Plan using neural provider if set, or deterministic rules."""
        if self._provider is not None:
            try:
                plan = self._generate_neural_plan(goal, available_tools, context)
                if plan is not None:
                    logger.info("Generated valid neural plan (%d steps) via provider '%s'", len(plan.steps), getattr(self._provider, "name", "custom"))
                    return plan
            except Exception as exc:
                logger.warning("Neural provider '%s' failed (%s).", getattr(self._provider, "name", "custom"), exc)
                if not self._enable_fallback:
                    raise

        logger.info("Using deterministic heuristic planner for goal '%s'", goal)
        return self._create_deterministic_plan(goal, available_tools, context)

    def _generate_neural_plan(
        self,
        goal: str,
        available_tools: list[ToolDescriptor],
        context: dict[str, Any] | None = None,
    ) -> Plan:
        """Execute neural provider in a background thread with strict timeout guard."""
        tool_descriptors_str = json.dumps([{"name": t.name, "description": t.description} for t in available_tools])
        prompt = f"Goal: {goal}\nAvailable Tools: {tool_descriptors_str}"

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(self._provider.generate_plan, prompt, context)
            raw_response = future.result(timeout=self._timeout_seconds)
            return PlanValidator.validate(raw_response, goal, available_tools)
        finally:
            executor.shutdown(wait=False)

    def _create_deterministic_plan(
        self,
        goal: str,
        available_tools: list[ToolDescriptor],
        context: dict[str, Any] | None = None,
    ) -> Plan:
        """Deterministic heuristic fallback rules."""
        goal_lower = re.sub(r"^iris,?\s*", "", goal.lower().strip(), flags=re.IGNORECASE).strip()
        steps: list[PlanStep] = []

        # 0. Conversational Identity Subsystem Queries
        if any(phrase in goal_lower for phrase in ("who is this", "who is that", "do you know him", "do you know her")):
            steps.append(PlanStep(1, "identity_tool", "Query current person identity", {"action": "query_current_person"}))
            return Plan(goal=goal, steps=steps)

        if "remember" in goal_lower:
            if "don't" in goal_lower or "do not" in goal_lower:
                steps.append(PlanStep(1, "identity_tool", "Reject person enrollment", {"action": "reject_person"}))
            else:
                match = re.search(r"as\s+([a-zA-Z]+)", goal_lower)
                name = match.group(1).capitalize() if match else goal_lower.replace("remember", "").strip().capitalize()
                steps.append(PlanStep(1, "identity_tool", f"Remember person as {name}", {"action": "remember_person", "name": name}))
            return Plan(goal=goal, steps=steps)

        if "forget" in goal_lower:
            if "everyone" in goal_lower or "all" in goal_lower:
                steps.append(PlanStep(1, "identity_tool", "Forget all remembered identities", {"action": "forget_all"}))
            else:
                name = goal_lower.replace("forget", "").strip().capitalize()
                steps.append(PlanStep(1, "identity_tool", f"Forget person {name}", {"action": "forget_person", "name": name}))
            return Plan(goal=goal, steps=steps)

        # 0. Conversational UI Screen Grounding Queries
        if any(phrase in goal_lower for phrase in ("find the", "find search", "find send", "where is the")):
            target_name = re.sub(r"^(find|where is)\s+(the|a|an)?\s*", "", goal_lower).strip()
            steps.append(PlanStep(1, "desktop_tool", f"Find UI element '{target_name}'", {"action": "find_element", "target": target_name}))
            return Plan(goal=goal, steps=steps)

        if any(term in goal_lower for term in ("this", "that", "here")) and any(cmd in goal_lower for cmd in ("click", "select", "right click")):
            steps.append(PlanStep(1, "desktop_tool", f"Gaze spatial click '{goal_lower}'", {"action": "spatial_click", "target": goal_lower}))
            return Plan(goal=goal, steps=steps)

        if "visible" in goal_lower or "what buttons" in goal_lower or "what is that button" in goal_lower:
            steps.append(PlanStep(1, "desktop_tool", "Query visible screen elements", {"action": "query_visible_elements"}))
            return Plan(goal=goal, steps=steps)

        if "click" in goal_lower and not any(app in goal_lower for app in ("chrome", "notepad", "calculator")):
            target_name = re.sub(r"^(click|select)\s+(the|a|an)?\s*", "", goal_lower).strip()
            steps.append(PlanStep(1, "desktop_tool", f"Click grounded UI element '{target_name}'", {"action": "click_grounded", "target": target_name}))
            return Plan(goal=goal, steps=steps)

        # 0a. Google account OAuth connection requests
        if any(phrase in goal_lower for phrase in ("connect my google", "connect google", "connect gmail", "connect my gmail", "connect my calendar", "login to google", "sign in to google")):
            steps.append(PlanStep(1, "desktop_tool", "Open Google OAuth authorization page in browser", {"action": "open_application", "target": "http://localhost:8000/api/auth/google/login"}))
            return Plan(goal=goal, steps=steps)

        # 0b. Triple-Service (Email + Calendar + GitHub) combined attention query
        if ("email" in goal_lower or "mail" in goal_lower) and ("calendar" in goal_lower or "meeting" in goal_lower or "schedule" in goal_lower) and ("github" in goal_lower or "repo" in goal_lower or "attention" in goal_lower):
            steps.append(PlanStep(1, "email_tool", "Check pending email attention items", {"action": "get_pending_attention"}))
            steps.append(PlanStep(2, "calendar_tool", "Check today's scheduled meetings", {"action": "get_today_events"}))
            steps.append(PlanStep(3, "github_tool", "Check GitHub repository activity summary", {"action": "get_activity_summary"}))
            return Plan(goal=goal, steps=steps)

        # 0c. Dual-Service GitHub + Email combined query
        if ("github" in goal_lower or "repo" in goal_lower) and ("email" in goal_lower or "mail" in goal_lower):
            steps.append(PlanStep(1, "github_tool", "Check GitHub repository activity summary", {"action": "get_activity_summary"}))
            steps.append(PlanStep(2, "email_tool", "Check important unread emails", {"action": "get_important_unread"}))
            return Plan(goal=goal, steps=steps)

        # 0b. Email queries
        if "email" in goal_lower or "mail" in goal_lower or "inbox" in goal_lower:
            if "important" in goal_lower or "urgent" in goal_lower:
                steps.append(PlanStep(1, "email_tool", "Get important unread emails", {"action": "get_important_unread"}))
            elif "pending" in goal_lower or "attention" in goal_lower:
                steps.append(PlanStep(1, "email_tool", "Get pending attention emails", {"action": "get_pending_attention"}))
            elif "search" in goal_lower or "from" in goal_lower:
                match = re.search(r"(search|from|about)\s+(.+)", goal_lower)
                query = match.group(2) if match else goal_lower
                steps.append(PlanStep(1, "email_tool", f"Search emails for '{query}'", {"action": "search_emails", "query": query}))
            else:
                steps.append(PlanStep(1, "email_tool", "Check unread email count", {"action": "get_unread_count"}))
            return Plan(goal=goal, steps=steps)

        # 0c. Calendar queries
        if "calendar" in goal_lower or "meeting" in goal_lower or "event" in goal_lower or "schedule" in goal_lower or "tomorrow" in goal_lower:
            if "next" in goal_lower:
                steps.append(PlanStep(1, "calendar_tool", "Get next upcoming meeting", {"action": "get_next_event"}))
            elif "tomorrow" in goal_lower:
                steps.append(PlanStep(1, "calendar_tool", "Get tomorrow's calendar events", {"action": "get_events_by_date", "date": "tomorrow"}))
            elif "upcoming" in goal_lower or "week" in goal_lower:
                steps.append(PlanStep(1, "calendar_tool", "Get upcoming schedule", {"action": "get_upcoming_events", "days": 7}))
            else:
                steps.append(PlanStep(1, "calendar_tool", "Get today's calendar events", {"action": "get_today_events"}))
            return Plan(goal=goal, steps=steps)

        # 0d. Remote GitHub queries (issues, PRs, workflow status, or explicit remote GitHub queries)
        if "github" in goal_lower and not ("completed" in goal_lower or "git status" in goal_lower):
            if "issue" in goal_lower:
                steps.append(PlanStep(1, "github_tool", "Check open GitHub issues", {"action": "get_issues"}))
            elif "commit" in goal_lower or "changed" in goal_lower:
                steps.append(PlanStep(1, "github_tool", "Fetch recent GitHub commits", {"action": "get_recent_commits", "count": 5}))
            elif "workflow" in goal_lower or "ci" in goal_lower or "actions" in goal_lower:
                steps.append(PlanStep(1, "github_tool", "Check GitHub Actions workflow status", {"action": "get_workflow_status"}))
            else:
                steps.append(PlanStep(1, "github_tool", "Check remote GitHub repository info", {"action": "get_repository_info"}))
            return Plan(goal=goal, steps=steps)

        # 1. Local Git repo progress query (e.g., "Check my GitHub repository and tell me what we've completed")
        if "completed" in goal_lower or "repository" in goal_lower or "git status" in goal_lower or "what we" in goal_lower:
            steps.append(PlanStep(1, "git_tool", "Check git repository status and branch", {"action": "get_status"}))
            steps.append(PlanStep(2, "git_tool", "Fetch recent commit history", {"action": "get_log", "count": 5}))
            steps.append(PlanStep(3, "filesystem_tool", "Read repository progress summary", {"action": "read_file", "path": ".ai/current_state.md"}))
            return Plan(goal=goal, steps=steps)

        # 2. Compound actions ("Open Notepad and type hello" or "Open Chrome and search for Python 3.14")
        compound_match = re.search(r"open\s+([\w\s]+?)\s+and\s+(type|write|tell|check|show|search)\s+(.+)", goal_lower)
        if compound_match:
            app_name = compound_match.group(1).strip()
            action_type = compound_match.group(2).strip()
            payload = compound_match.group(3).strip()

            steps.append(PlanStep(1, "desktop_tool", f"Open application '{app_name}'", {"action": "open_application", "target": app_name}))
            if action_type in ("type", "write"):
                steps.append(PlanStep(2, "desktop_tool", f"Type text '{payload}'", {"action": "type_text", "text": payload}))
            elif action_type == "search" or "search" in payload:
                query_str = re.sub(r"^for\s+", "", payload, flags=re.IGNORECASE).strip()
                steps.append(PlanStep(2, "web_search_tool", f"Search web for '{query_str}'", {"action": "search", "query": query_str}))
            elif "files" in payload or "changed" in payload or "git" in payload:
                steps.append(PlanStep(2, "git_tool", "Check git status for modified files", {"action": "get_status"}))
            else:
                steps.append(PlanStep(2, "desktop_tool", f"Execute action '{action_type} {payload}'", {"action": "type_text", "text": payload}))
            return Plan(goal=goal, steps=steps)

        # 3. Delete file request (Confirmation Required)
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

        # 8. Canonical Voice Intent Resolution (Single Action Desktop Intent)
        parsed_intent = self._intent_parser.parse(goal_lower)
        if parsed_intent.intent != VoiceIntentType.NO_INTENT:
            if parsed_intent.intent in (VoiceIntentType.OPEN_APPLICATION, VoiceIntentType.OPEN_CHROME, VoiceIntentType.OPEN_NOTEPAD):
                app_target = parsed_intent.target or ("chrome" if parsed_intent.intent == VoiceIntentType.OPEN_CHROME else ("notepad" if parsed_intent.intent == VoiceIntentType.OPEN_NOTEPAD else goal_lower))
                steps.append(PlanStep(1, "desktop_tool", f"Open application '{app_target}'", {"action": "open_application", "target": app_target}))
                return Plan(goal=goal, steps=steps)
            elif parsed_intent.intent == VoiceIntentType.RIGHT_CLICK:
                steps.append(PlanStep(1, "desktop_tool", "Execute right click", {"action": "right_click"}))
                return Plan(goal=goal, steps=steps)
            elif parsed_intent.intent == VoiceIntentType.DOUBLE_CLICK:
                steps.append(PlanStep(1, "desktop_tool", "Execute double click", {"action": "double_click"}))
                return Plan(goal=goal, steps=steps)
            elif parsed_intent.intent == VoiceIntentType.PRIMARY_CLICK:
                steps.append(PlanStep(1, "desktop_tool", "Execute left click", {"action": "click"}))
                return Plan(goal=goal, steps=steps)
            elif parsed_intent.intent == VoiceIntentType.COPY:
                steps.append(PlanStep(1, "desktop_tool", "Copy selection to clipboard", {"action": "copy"}))
                return Plan(goal=goal, steps=steps)
            elif parsed_intent.intent == VoiceIntentType.PASTE:
                steps.append(PlanStep(1, "desktop_tool", "Paste clipboard content", {"action": "paste"}))
                return Plan(goal=goal, steps=steps)
            elif parsed_intent.intent == VoiceIntentType.SCROLL_DOWN:
                steps.append(PlanStep(1, "desktop_tool", "Scroll down", {"action": "scroll_down"}))
                return Plan(goal=goal, steps=steps)
            elif parsed_intent.intent == VoiceIntentType.SCROLL_UP:
                steps.append(PlanStep(1, "desktop_tool", "Scroll up", {"action": "scroll_up"}))
                return Plan(goal=goal, steps=steps)
            elif parsed_intent.intent == VoiceIntentType.TYPE_TEXT:
                text_payload = parsed_intent.query or parsed_intent.params.get("text") or re.sub(r"^(type|write|say)\s+", "", goal_lower, flags=re.IGNORECASE).strip()
                steps.append(PlanStep(1, "desktop_tool", f"Type text '{text_payload}'", {"action": "type_text", "text": text_payload}))
                return Plan(goal=goal, steps=steps)
            elif parsed_intent.intent == VoiceIntentType.CLOSE_WINDOW:
                steps.append(PlanStep(1, "desktop_tool", "Close active window", {"action": "close_window"}))
                return Plan(goal=goal, steps=steps)
            elif parsed_intent.intent == VoiceIntentType.MINIMIZE_WINDOW:
                steps.append(PlanStep(1, "desktop_tool", "Minimize active window", {"action": "minimize_window"}))
                return Plan(goal=goal, steps=steps)

        # 9. Default single-step desktop UI action
        clean_target = re.sub(r"^(open|launch|start)\s+", "", goal_lower, flags=re.IGNORECASE).strip()
        steps.append(PlanStep(1, "desktop_tool", f"Open application '{clean_target}'", {"action": "open_application", "target": clean_target}))
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
