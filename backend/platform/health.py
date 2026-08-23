"""Subsystem Component Health Monitoring Service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
import time
from typing import Any

from backend.core.events.bus import EventBus
from backend.platform.runtime_events import HealthStatusChangedEvent
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class HealthState(str, Enum):
    """Component health status enumeration."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


@dataclass
class ComponentStatus:
    """Readiness/liveness status snapshot for a single subsystem component."""

    component_name: str
    state: HealthState = HealthState.HEALTHY
    details: dict[str, Any] = field(default_factory=dict)
    last_checked: float = field(default_factory=time.time)


class HealthMonitor:
    """Central service managing subsystem probes and component health state transitions."""

    def __init__(self, event_bus: EventBus | None = None, enabled: bool = True) -> None:
        self._event_bus = event_bus
        self._enabled = enabled
        self._statuses: dict[str, ComponentStatus] = {}
        self._probes: dict[str, Callable[[], tuple[HealthState, dict[str, Any]]]] = {}
        self._lock = RLock()

    @property
    def enabled(self) -> bool:
        """Return whether health monitor is active."""
        return self._enabled

    def register_probe(
        self,
        component_name: str,
        probe_fn: Callable[[], tuple[HealthState, dict[str, Any]]],
    ) -> None:
        """Register a health probe callback for a named component."""
        with self._lock:
            self._probes[component_name] = probe_fn
            self._statuses[component_name] = ComponentStatus(
                component_name=component_name,
                state=HealthState.HEALTHY,
                details={"registered": True},
                last_checked=time.time(),
            )

    def check_component(self, component_name: str) -> ComponentStatus:
        """Execute registered probe for a specific component."""
        with self._lock:
            probe = self._probes.get(component_name)
            if not probe:
                return ComponentStatus(
                    component_name=component_name,
                    state=HealthState.UNHEALTHY,
                    details={"error": "No probe registered"},
                    last_checked=time.time(),
                )

            try:
                state, details = probe()
            except Exception as exc:
                state = HealthState.UNHEALTHY
                details = {"error": str(exc)}

            old_status = self._statuses.get(component_name)
            old_state = old_status.state if old_status else HealthState.HEALTHY

            new_status = ComponentStatus(
                component_name=component_name,
                state=state,
                details=details,
                last_checked=time.time(),
            )
            self._statuses[component_name] = new_status

            if old_state != state:
                logger.info("Health status change for '%s': %s -> %s", component_name, old_state.value, state.value)
                if self._event_bus:
                    self._event_bus.publish(
                        HealthStatusChangedEvent(
                            component_name=component_name,
                            old_status=old_state.value,
                            new_status=state.value,
                            reason=details.get("error", "Probe evaluation"),
                        )
                    )

            return new_status

    def check_all(self) -> dict[str, ComponentStatus]:
        """Execute probes for all registered components and return updated status map."""
        with self._lock:
            for name in list(self._probes.keys()):
                self.check_component(name)
            return dict(self._statuses)

    def get_overall_health(self) -> HealthState:
        """Evaluate aggregate system health state across all components."""
        with self._lock:
            states = [s.state for s in self._statuses.values()]
            if HealthState.UNHEALTHY in states:
                return HealthState.UNHEALTHY
            if HealthState.DEGRADED in states:
                return HealthState.DEGRADED
            return HealthState.HEALTHY
