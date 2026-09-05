"""Unit tests for Sprint 12 Runtime Platform & Production Hardening Layer."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config.settings import settings
from backend.core.di.container import build_container
from backend.core.events.bus import EventBus
from backend.sys_platform.config_validator import ConfigurationValidator
from backend.sys_platform.diagnostics import DiagnosticsService
from backend.sys_platform.health import HealthMonitor, HealthState
from backend.sys_platform.lifecycle import LifecycleManager, RecoveryManager
from backend.sys_platform.metrics import MetricsRegistry, PerformanceMonitor
from backend.sys_platform.runtime_events import (
    HealthStatusChangedEvent,
    RuntimeRecoveryTriggeredEvent,
)


def test_health_monitor_probes_and_events():
    event_bus = EventBus()
    events_captured = []
    event_bus.subscribe(HealthStatusChangedEvent, lambda e: events_captured.append(e))

    monitor = HealthMonitor(event_bus=event_bus, enabled=True)
    status_holder = {"healthy": True}

    def _sample_probe():
        if status_holder["healthy"]:
            return HealthState.HEALTHY, {"status": "ok"}
        return HealthState.UNHEALTHY, {"error": "down"}

    monitor.register_probe("sample_service", _sample_probe)
    initial = monitor.check_component("sample_service")
    assert initial.state == HealthState.HEALTHY

    # Trigger state change
    status_holder["healthy"] = False
    updated = monitor.check_component("sample_service")
    assert updated.state == HealthState.UNHEALTHY
    assert monitor.get_overall_health() == HealthState.UNHEALTHY

    assert len(events_captured) == 1
    assert events_captured[0].component_name == "sample_service"
    assert events_captured[0].new_status == "UNHEALTHY"


def test_configuration_validator():
    valid, errors = ConfigurationValidator.validate_settings(settings)
    assert valid is True
    assert len(errors) == 0


def test_metrics_registry_and_performance_monitor():
    event_bus = EventBus()
    metrics = MetricsRegistry(enabled=True)
    _monitor = PerformanceMonitor(metrics_registry=metrics, event_bus=event_bus)

    metrics.increment_counter("test_counter", 5.0)
    metrics.set_gauge("test_gauge", 42.0)
    metrics.record_timer("test_timer", 12.5)

    summary = metrics.get_metrics_summary()
    assert summary["counters"]["test_counter"] == 5.0
    assert summary["gauges"]["test_gauge"] == 42.0
    assert summary["timers"]["test_timer"]["count"] == 1.0
    assert summary["timers"]["test_timer"]["avg_ms"] == 12.5


def test_diagnostics_service_snapshot():
    monitor = HealthMonitor(enabled=True)
    monitor.register_probe("test_comp", lambda: (HealthState.HEALTHY, {}))
    metrics = MetricsRegistry(enabled=True)

    diagnostics = DiagnosticsService(health_monitor=monitor, metrics_registry=metrics)
    snapshot = diagnostics.generate_snapshot()

    assert "uptime_seconds" in snapshot
    assert snapshot["overall_health"] == "HEALTHY"
    assert "test_comp" in snapshot["components"]


def test_lifecycle_and_recovery_managers():
    event_bus = EventBus()
    captured_events = []
    event_bus.subscribe(RuntimeRecoveryTriggeredEvent, lambda e: captured_events.append(e))

    lifecycle = LifecycleManager(event_bus=event_bus)
    started = []
    stopped = []

    lifecycle.register_startup_hook("s1", lambda: started.append("s1"))
    lifecycle.register_shutdown_hook("d1", lambda: stopped.append("d1"))

    lifecycle.startup()
    assert started == ["s1"]

    lifecycle.shutdown()
    assert stopped == ["d1"]

    recovery = RecoveryManager(event_bus=event_bus)
    recovery.register_recovery_strategy("failing_service", lambda: True)
    success = recovery.attempt_recovery("failing_service")
    assert success is True
    assert len(captured_events) == 1
    assert captured_events[0].component_name == "failing_service"


def test_di_container_wires_runtime_platform():
    container = build_container(settings)
    assert container.health_monitor is not None
    assert container.metrics_registry is not None
    assert container.diagnostics_service is not None
    assert container.lifecycle_manager is not None
    assert container.recovery_manager is not None


def test_runtime_platform_api_routes():
    app = create_app()
    client = TestClient(app)

    res_health = client.get("/api/v1/health")
    assert res_health.status_code == 200
    data_health = res_health.json()
    assert "overall_health" in data_health

    res_metrics = client.get("/api/v1/metrics")
    assert res_metrics.status_code == 200
    data_metrics = res_metrics.json()
    assert "counters" in data_metrics
