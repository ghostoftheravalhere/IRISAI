"""PlannerBenchmark interface for evaluating and comparing Deterministic vs Neural Local LLM Planners."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any

from backend.agent.planner import PlanValidationError, Planner
from backend.agent.tool_registry import ToolDescriptor
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BenchmarkTask:
    """Individual benchmark test goal evaluation case."""

    goal: str
    expected_tools: list[str] = field(default_factory=list)
    min_steps: int = 1
    max_steps: int = 5


@dataclass
class BenchmarkResult:
    """Aggregated benchmark statistics and performance metrics."""

    total_tasks: int = 0
    valid_json_count: int = 0
    valid_schema_count: int = 0
    correct_tool_count: int = 0
    fallback_count: int = 0
    policy_violation_count: int = 0
    malformed_output_count: int = 0
    total_latency_ms: float = 0.0

    @property
    def valid_json_rate(self) -> float:
        return (self.valid_json_count / self.total_tasks) * 100.0 if self.total_tasks > 0 else 0.0

    @property
    def valid_schema_rate(self) -> float:
        return (self.valid_schema_count / self.total_tasks) * 100.0 if self.total_tasks > 0 else 0.0

    @property
    def tool_accuracy_rate(self) -> float:
        return (self.correct_tool_count / self.total_tasks) * 100.0 if self.total_tasks > 0 else 0.0

    @property
    def fallback_rate(self) -> float:
        return (self.fallback_count / self.total_tasks) * 100.0 if self.total_tasks > 0 else 0.0

    @property
    def malformed_output_rate(self) -> float:
        return (self.malformed_output_count / self.total_tasks) * 100.0 if self.total_tasks > 0 else 0.0

    @property
    def average_latency_ms(self) -> float:
        return (self.total_latency_ms / self.total_tasks) if self.total_tasks > 0 else 0.0


class PlannerBenchmark:
    """Benchmark suite runner for evaluating planner output quality, schema compliance, latency, and fallback rates."""

    def __init__(self, tasks: list[BenchmarkTask] | None = None) -> None:
        self._tasks = tasks or self._default_benchmark_tasks()

    def _default_benchmark_tasks(self) -> list[BenchmarkTask]:
        return [
            BenchmarkTask("Open Chrome.", expected_tools=["desktop_tool", "browser_tool"]),
            BenchmarkTask("Open Notepad and type hello.", expected_tools=["desktop_tool"]),
            BenchmarkTask("Find my project report.", expected_tools=["filesystem_tool"]),
            BenchmarkTask("Check the repository and summarize recent work.", expected_tools=["git_tool", "filesystem_tool"]),
            BenchmarkTask("Search the web for Python 3.14 and summarize it.", expected_tools=["web_search_tool", "browser_tool"]),
            BenchmarkTask("Copy this and paste it there.", expected_tools=["desktop_tool"]),
        ]

    def run_eval(
        self,
        planner: Planner,
        available_tools: list[ToolDescriptor],
        context: dict[str, Any] | None = None,
    ) -> BenchmarkResult:
        """Run benchmark evaluation suite over configured tasks."""
        res = BenchmarkResult(total_tasks=len(self._tasks))

        for task in self._tasks:
            start_time = time.perf_counter()
            try:
                plan = planner.create_plan(task.goal, available_tools, context)
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                res.total_latency_ms += latency_ms

                res.valid_json_count += 1
                res.valid_schema_count += 1

                # Check tool selection alignment
                used_tools = {step.tool_name.lower() for step in plan.steps}
                if any(expected.lower() in used_tools for expected in task.expected_tools):
                    res.correct_tool_count += 1

            except PlanValidationError as val_err:
                res.malformed_output_count += 1
                logger.warning("Benchmark task '%s' failed validation: %s", task.goal, val_err)
            except Exception as exc:
                res.fallback_count += 1
                logger.warning("Benchmark task '%s' encountered execution exception: %s", task.goal, exc)

        return res

    def compare_plans(
        self,
        goal: str,
        neural_planner: Planner,
        deterministic_planner: Planner,
        available_tools: list[ToolDescriptor],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Compare neural model plan vs deterministic plan for a single user goal."""
        t0 = time.perf_counter()
        det_plan = deterministic_planner.create_plan(goal, available_tools, context)
        det_latency_ms = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        neural_plan = neural_planner.create_plan(goal, available_tools, context)
        neural_latency_ms = (time.perf_counter() - t1) * 1000.0

        return {
            "goal": goal,
            "deterministic": {
                "steps_count": len(det_plan.steps),
                "tools": [s.tool_name for s in det_plan.steps],
                "latency_ms": round(det_latency_ms, 2),
            },
            "neural": {
                "steps_count": len(neural_plan.steps),
                "tools": [s.tool_name for s in neural_plan.steps],
                "latency_ms": round(neural_latency_ms, 2),
            },
        }
