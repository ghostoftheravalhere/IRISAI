"""Domain events emitted by the Brain Orchestrator."""

from __future__ import annotations

from dataclasses import dataclass

from backend.core.events.bus import DomainEvent


@dataclass
class OrchestrationRequestedEvent(DomainEvent):
    """Event emitted when a command is submitted to the Brain Orchestrator."""

    source: str = "voice"
    intent: str = ""
    raw_payload: str = ""


@dataclass
class OrchestrationCompletedEvent(DomainEvent):
    """Event emitted when the Brain Orchestrator successfully completes an action."""

    intent: str = ""
    action: str = ""
    success: bool = True
    execution_message: str = ""
    latency_ms: float = 0.0


@dataclass
class OrchestrationBlockedEvent(DomainEvent):
    """Event emitted when safety policies block an orchestration request."""

    intent: str = ""
    reason: str = ""
    policy_name: str = ""
