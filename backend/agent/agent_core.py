"""AgentCore: Main orchestrator for goal understanding, multi-step planning, tool execution loops, security policy validation, short-term task memory, and natural response synthesis."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any

from backend.agent.dataset.collector import InteractionDatasetCollector
from backend.agent.planner import Planner
from backend.agent.policy_engine import PolicyEngine
from backend.agent.response_generator import ResponseGenerator
from backend.agent.task_state import PlanStep, TaskState, TaskStatus
from backend.agent.tool_executor import ToolExecutor
from backend.agent.tool_registry import Tool, ToolRegistry, ToolResult
from backend.agent.tools.browser_tool import BrowserTool
from backend.agent.tools.desktop_tool import DesktopTool
from backend.agent.tools.filesystem_tool import FilesystemTool
from backend.agent.tools.git_tool import GitTool
from backend.agent.tools.web_search_tool import WebSearchTool
from backend.automation.action_engine import ActionEngine
from backend.brain.dialogue_manager import DialogueManager
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AgentResult:
    """Consolidated outcome returned by AgentCore execution."""

    success: bool
    response: str
    task_state: TaskState
    error_code: str | None = None


class AgentCore:
    """Main Agent Core Orchestrator coordinating task planning, security gates, tool feedback loops, transient task memory, and natural response generation."""

    def __init__(
        self,
        tool_registry: ToolRegistry | None = None,
        tool_executor: ToolExecutor | None = None,
        planner: Planner | None = None,
        policy_engine: PolicyEngine | None = None,
        response_generator: ResponseGenerator | None = None,
        dialogue_manager: DialogueManager | None = None,
        action_engine: ActionEngine | None = None,
        collector: InteractionDatasetCollector | None = None,
    ) -> None:
        self._registry = tool_registry or ToolRegistry()
        self._policy_engine = policy_engine or PolicyEngine()
        self._executor = tool_executor or ToolExecutor(self._registry, self._policy_engine)
        self._planner = planner or Planner()
        self._response_gen = response_generator or ResponseGenerator()
        self._dialogue_manager = dialogue_manager
        self._collector = collector or InteractionDatasetCollector()
        self._active_task_state: TaskState | None = None
        self._lock = RLock()

        # Register standard built-in tools
        self._register_default_tools(action_engine)

    def _register_default_tools(self, action_engine: ActionEngine | None = None) -> None:
        """Register default initial core tool suite."""
        from backend.agent.tools.email_tool import EmailTool
        from backend.agent.tools.calendar_tool import CalendarTool
        from backend.agent.tools.github_tool import GitHubTool

        dt = DesktopTool(action_engine=action_engine)
        ft = FilesystemTool()
        gt = GitTool()
        wst = WebSearchTool()
        bt = BrowserTool(action_engine=action_engine)
        et = EmailTool()
        ct = CalendarTool()
        ght = GitHubTool()

        self._registry.register_tool(dt)
        self._registry.register_tool(ft)
        self._registry.register_tool(gt)
        self._registry.register_tool(wst)
        self._registry.register_tool(bt)
        self._registry.register_tool(et)
        self._registry.register_tool(ct)
        self._registry.register_tool(ght)

    def register_custom_tool(self, tool: Tool) -> bool:
        """Register a custom tool capability."""
        return self._registry.register_tool(tool)

    @property
    def active_task_state(self) -> TaskState | None:
        """Return active transient task state."""
        return self._active_task_state

    def process_goal(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
        skip_confirmation: bool = False,
    ) -> AgentResult:
        """Process user goal through planning, security policy evaluation, tool feedback loops, task memory, and response synthesis."""
        with self._lock:
            # 1. Handle follow-up candidate selection ("the second one", "the first one")
            if self._active_task_state and self._active_task_state.candidates:
                goal_lower = goal.lower()
                if any(k in goal_lower for k in ("second", "first", "1st", "2nd", "the one", "that one")):
                    resolved = self._active_task_state.resolve_candidate(goal)
                    if resolved:
                        logger.info("Resolved candidate from follow-up query '%s': %s", goal, resolved)
                        read_step = PlanStep(
                            step_id=1,
                            tool_name="filesystem_tool",
                            description=f"Read resolved file '{resolved['name']}'",
                            params={"action": "read_file", "path": resolved["path"]},
                        )
                        res, _ = self._executor.execute_tool("filesystem_tool", read_step.params, task_state=self._active_task_state)
                        self._active_task_state.advance_step(read_step, res)
                        resp = self._response_gen.generate_final_response(self._active_task_state)
                        return AgentResult(True, resp, self._active_task_state)

            # 2. Initialize new TaskState or retain follow-up context
            merged_context = dict(context or {})
            if self._active_task_state:
                merged_context["last_resolved_target"] = self._active_task_state.last_resolved_target
                merged_context["last_goal"] = self._active_task_state.user_goal
                if self._active_task_state.active_application:
                    merged_context["active_app"] = self._active_task_state.active_application

            task_state = TaskState(user_goal=goal, status=TaskStatus.PLANNING)
            self._active_task_state = task_state
            logger.info("AgentCore processing goal: '%s' (task_id=%s)", goal, task_state.task_id)

            # 3. Generate plan
            available_tools = self._registry.list_descriptors()
            plan = self._planner.create_plan(goal, available_tools, merged_context)
            task_state.current_plan = plan
            task_state.status = TaskStatus.EXECUTING

            logger.info("Generated plan with %d steps for goal '%s'", len(plan.steps), goal)

            # 4. Multi-step execution loop
            while task_state.current_step_index < len(plan.steps):
                step = plan.steps[task_state.current_step_index]
                step.status = "IN_PROGRESS"
                logger.info("Executing plan step %d/%d: '%s' (tool=%s)", step.step_id, len(plan.steps), step.description, step.tool_name)

                # Execute step via ToolExecutor
                result, eval_res = self._executor.execute_tool(
                    step.tool_name,
                    step.params,
                    task_state=task_state,
                    skip_confirmation=skip_confirmation,
                )

                # Check policy evaluation
                if eval_res.requires_user_confirmation and result.error_code == "CONFIRMATION_REQUIRED":
                    task_state.status = TaskStatus.WAITING_CONFIRMATION
                    task_state.pending_confirmation = {
                        "tool_name": step.tool_name,
                        "params": step.params,
                        "step_id": step.step_id,
                    }
                    prompt = self._response_gen.generate_confirmation_prompt(step.tool_name, step.params, eval_res.reason)
                    logger.info("AgentCore waiting for user confirmation: %s", prompt)
                    agent_res = AgentResult(
                        success=False,
                        response=prompt,
                        task_state=task_state,
                        error_code="CONFIRMATION_REQUIRED",
                    )
                    self._collector.record_interaction(task_state, agent_res)
                    return agent_res

                # Evaluate step outcome feedback loop
                decision = self._planner.evaluate_step_result(step, result, task_state)
                task_state.advance_step(step, result)

                if decision == "STOP_FAILED":
                    task_state.fail_task(result.message)
                    resp = self._response_gen.generate_final_response(task_state)
                    agent_res = AgentResult(False, resp, task_state, error_code=result.error_code)
                    self._collector.record_interaction(task_state, agent_res)
                    return agent_res

                if decision == "REPLAN":
                    logger.info("Plan dynamically adjusted. Continuing execution with updated steps.")

            # 5. Plan completed successfully
            task_state.status = TaskStatus.COMPLETED
            resp = self._response_gen.generate_final_response(task_state)
            logger.info("AgentCore successfully completed task '%s'", task_state.task_id)
            agent_res = AgentResult(True, resp, task_state)
            self._collector.record_interaction(task_state, agent_res)
            return agent_res

    def resume_task_with_confirmation(self, task_state: TaskState, confirmed: bool) -> AgentResult:
        """Resume execution of a task paused for user confirmation."""
        with self._lock:
            if not confirmed:
                task_state.fail_task("User cancelled proposed action")
                agent_res = AgentResult(False, "Action cancelled by user.", task_state, error_code="CANCELLED")
                self._collector.record_interaction(task_state, agent_res)
                return agent_res

            task_state.status = TaskStatus.EXECUTING
            task_state.pending_confirmation = None
            goal = task_state.user_goal
            # Re-run current step skipping confirmation
            return self.process_goal(goal, skip_confirmation=True)
