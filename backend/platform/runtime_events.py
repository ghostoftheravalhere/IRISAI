"""Domain events emitted by the Runtime Platform & Production Hardening layer."""

from __future__ import annotations

from dataclasses import dataclass

from backend.core.events.bus import DomainEvent


@dataclass
class HealthStatusChangedEvent(DomainEvent):
    """Event emitted when a subsystem component health status changes."""

    component_name: str = ""
    old_status: str = "HEALTHY"
    new_status: str = "HEALTHY"
    reason: str = ""


@dataclass
class ConfigurationValidationErrorEvent(DomainEvent):
    """Event emitted when pre-boot configuration validation encounters an error."""

    setting_key: str = ""
    error_message: str = ""


@dataclass
class RuntimeRecoveryTriggeredEvent(DomainEvent):
    """Event emitted when a recovery strategy is executed for a component."""

    component_name: str = ""
    action_taken: str = ""


@dataclass
class ShutdownInitiatedEvent(DomainEvent):
    """Event emitted when graceful application shutdown is triggered."""

    reason: str = "normal"
