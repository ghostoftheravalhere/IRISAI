"""Safe ToolExecutor runner handling security policy validation, timeouts, and exception management."""

from __future__ import annotations

import concurrent.futures
from typing import Any

from backend.agent.policy_engine import PolicyEngine, PolicyEvaluationResult
from backend.agent.task_state import TaskState
from backend.agent.tool_registry import ToolRegistry, ToolResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ToolExecutor:
    """Executes registered tools through policy gates with timeout guards and error wrapping."""

    def __init__(
        self,
        registry: ToolRegistry,
        policy_engine: PolicyEngine | None = None,
        default_timeout_seconds: float = 10.0,
    ) -> None:
        self._registry = registry
        self._policy_engine = policy_engine or PolicyEngine()
        self._default_timeout = default_timeout_seconds

    def execute_tool(
        self,
        tool_name: str,
        params: dict[str, Any],
        task_state: TaskState | None = None,
        skip_confirmation: bool = False,
    ) -> tuple[ToolResult, PolicyEvaluationResult]:
        """Validate policy and execute target tool safely."""
        tool = self._registry.get_tool(tool_name)
        if tool is None:
            err_msg = f"Tool '{tool_name}' is not registered in ToolRegistry"
            logger.error(err_msg)
            eval_res = PolicyEvaluationResult(
                allowed=False,
                permission_level=self._policy_engine._evaluate_level(tool_name) if hasattr(self._policy_engine, "_evaluate_level") else None,
                requires_user_confirmation=False,
                reason=err_msg,
            )
            return ToolResult(False, err_msg, error_code="TOOL_NOT_FOUND"), eval_res

        desc = tool.descriptor
        eval_res = self._policy_engine.evaluate(desc.name, desc.permission_level, params)

        if not eval_res.allowed:
            logger.warning("Policy evaluation denied execution for tool '%s': %s", desc.name, eval_res.reason)
            return ToolResult(False, f"Policy denied execution: {eval_res.reason}", error_code="POLICY_DENIED"), eval_res

        if eval_res.requires_user_confirmation and not skip_confirmation:
            logger.info("Tool '%s' requires user confirmation before execution", desc.name)
            return ToolResult(
                False,
                f"Confirmation required: {eval_res.reason}",
                data={"requires_confirmation": True, "tool_name": desc.name, "params": params},
                error_code="CONFIRMATION_REQUIRED",
            ), eval_res

        # Execute tool inside thread pool with timeout guard
        logger.info("Executing Tool '%s' (params=%s)", desc.name, params)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(tool.execute, params, task_state)
                result = future.result(timeout=self._default_timeout)
                return result, eval_res
        except concurrent.futures.TimeoutError:
            err_msg = f"Tool '{desc.name}' execution timed out after {self._default_timeout}s"
            logger.error(err_msg)
            return ToolResult(False, err_msg, error_code="TIMEOUT"), eval_res
        except Exception as exc:
            err_msg = f"Tool '{desc.name}' failed with unhandled exception: {exc}"
            logger.exception(err_msg)
            return ToolResult(False, err_msg, error_code="EXECUTION_EXCEPTION"), eval_res

    def execute_tools_parallel(
        self,
        tool_calls: list[tuple[str, dict[str, Any]]],
        task_state: TaskState | None = None,
        skip_confirmation: bool = False,
    ) -> list[tuple[ToolResult, PolicyEvaluationResult]]:
        """Execute multiple independent SAFE tools concurrently while preserving order and isolation."""
        if not tool_calls:
            return []

        if len(tool_calls) == 1:
            tool_name, params = tool_calls[0]
            return [self.execute_tool(tool_name, params, task_state=task_state, skip_confirmation=skip_confirmation)]

        logger.info("Executing %d independent tools in parallel", len(tool_calls))
        results: list[tuple[ToolResult, PolicyEvaluationResult] | None] = [None] * len(tool_calls)

        def _worker(idx: int, t_name: str, t_params: dict[str, Any]):
            try:
                res = self.execute_tool(t_name, t_params, task_state=task_state, skip_confirmation=skip_confirmation)
                return idx, res
            except Exception as exc:
                logger.exception("Parallel worker for tool '%s' failed: %s", t_name, exc)
                err_res = ToolResult(False, f"Tool '{t_name}' unhandled exception: {exc}", error_code="PARALLEL_EXECUTION_ERROR")
                eval_res = PolicyEvaluationResult(allowed=True, permission_level=None, requires_user_confirmation=False, reason="Exception")
                return idx, (err_res, eval_res)

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(tool_calls), 8)) as pool:
            futures = [pool.submit(_worker, i, name, params) for i, (name, params) in enumerate(tool_calls)]
            for future in concurrent.futures.as_completed(futures):
                try:
                    idx, res = future.result()
                    results[idx] = res
                except Exception as exc:
                    logger.error("Error retrieving parallel future result: %s", exc)

        final_results: list[tuple[ToolResult, PolicyEvaluationResult]] = []
        for i, res in enumerate(results):
            if res is not None:
                final_results.append(res)
            else:
                t_name, _ = tool_calls[i]
                final_results.append((
                    ToolResult(False, f"Tool '{t_name}' parallel execution failed", error_code="PARALLEL_FAILED"),
                    PolicyEvaluationResult(allowed=False, permission_level=None, requires_user_confirmation=False, reason="Unassigned result"),
                ))

        return final_results
