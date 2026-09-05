"""Diagnostics Service aggregating health, metrics, and system status into unified snapshots."""

from __future__ import annotations

import time
from typing import Any

from backend.sys_platform.health import HealthMonitor
from backend.sys_platform.metrics import MetricsRegistry


class DiagnosticsService:
    """Aggregates health, metrics, configuration, and uptime into diagnostic snapshots."""

    def __init__(
        self,
        health_monitor: HealthMonitor | None = None,
        metrics_registry: MetricsRegistry | None = None,
    ) -> None:
        self._health_monitor = health_monitor
        self._metrics_registry = metrics_registry
        self._start_time = time.time()

    @property
    def uptime_seconds(self) -> float:
        """Return application uptime in seconds."""
        return time.time() - self._start_time

    def generate_snapshot(self) -> dict[str, Any]:
        """Generate a complete diagnostic snapshot dictionary."""
        health_data = {}
        overall_health = "UNKNOWN"
        if self._health_monitor:
            overall_health = self._health_monitor.get_overall_health().value
            health_data = {
                name: {
                    "state": status.state.value,
                    "details": status.details,
                    "last_checked": status.last_checked,
                }
                for name, status in self._health_monitor.check_all().items()
            }

        metrics_data = {}
        if self._metrics_registry:
            metrics_data = self._metrics_registry.get_metrics_summary()

        return {
            "uptime_seconds": self.uptime_seconds,
            "overall_health": overall_health,
            "components": health_data,
            "metrics": metrics_data,
            "timestamp": time.time(),
        }
