"""Operational Metrics Registry and Performance Monitor services."""

from __future__ import annotations

from collections import defaultdict
from threading import RLock
from typing import Any

from backend.brain.reasoning.events import ReasoningCompletedEvent
from backend.brain.skills.events import SkillExecutionCompletedEvent
from backend.brain.workflow_events import WorkflowCompletedEvent, WorkflowStartedEvent
from backend.core.events.bus import EventBus
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class MetricsRegistry:
    """In-memory metrics repository maintaining counters, gauges, and latency statistics."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = {}
        self._timers: dict[str, list[float]] = defaultdict(list)
        self._lock = RLock()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def increment_counter(self, name: str, value: float = 1.0) -> None:
        """Increment a metric counter."""
        if not self._enabled:
            return
        with self._lock:
            self._counters[name] += value

    def set_gauge(self, name: str, value: float) -> None:
        """Set a metric gauge value."""
        if not self._enabled:
            return
        with self._lock:
            self._gauges[name] = value

    def record_timer(self, name: str, duration_ms: float) -> None:
        """Record execution duration timing in milliseconds."""
        if not self._enabled:
            return
        with self._lock:
            self._timers[name].append(duration_ms)
            # Keep rolling window of last 100 entries
            if len(self._timers[name]) > 100:
                self._timers[name].pop(0)

    def get_metrics_summary(self) -> dict[str, Any]:
        """Return a snapshot summary of all recorded metrics."""
        with self._lock:
            timer_summary: dict[str, dict[str, float]] = {}
            for k, vals in self._timers.items():
                if vals:
                    timer_summary[k] = {
                        "count": float(len(vals)),
                        "avg_ms": sum(vals) / len(vals),
                        "max_ms": max(vals),
                        "min_ms": min(vals),
                    }

            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "timers": timer_summary,
            }


class PerformanceMonitor:
    """Subscribes to EventBus domain events to automatically record performance metrics."""

    def __init__(self, metrics_registry: MetricsRegistry, event_bus: EventBus | None = None) -> None:
        self._metrics = metrics_registry
        self._event_bus = event_bus

        if self._event_bus:
            self._event_bus.subscribe(WorkflowStartedEvent, self._on_workflow_started)
            self._event_bus.subscribe(WorkflowCompletedEvent, self._on_workflow_completed)
            self._event_bus.subscribe(SkillExecutionCompletedEvent, self._on_skill_completed)
            self._event_bus.subscribe(ReasoningCompletedEvent, self._on_reasoning_completed)

    def _on_workflow_started(self, event: WorkflowStartedEvent) -> None:
        self._metrics.increment_counter("workflows_started_total")

    def _on_workflow_completed(self, event: WorkflowCompletedEvent) -> None:
        self._metrics.increment_counter("workflows_completed_total")

    def _on_skill_completed(self, event: SkillExecutionCompletedEvent) -> None:
        self._metrics.increment_counter("skills_executed_total")
        self._metrics.record_timer(f"skill_{event.skill_id}_latency_ms", event.execution_time_ms)

    def _on_reasoning_completed(self, event: ReasoningCompletedEvent) -> None:
        self._metrics.increment_counter("reasoning_plans_generated_total")
        self._metrics.record_timer("reasoning_latency_ms", event.latency_ms)
