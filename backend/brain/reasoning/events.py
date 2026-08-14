"""Domain events emitted during AI Reasoning and Planning generation."""

from __future__ import annotations

from dataclasses import dataclass

from backend.core.events.bus import DomainEvent


@dataclass
class ReasoningStartedEvent(DomainEvent):
    """Event emitted when LLM plan generation begins."""

    user_prompt: str = ""
    provider_name: str = "mock"


@dataclass
class ReasoningCompletedEvent(DomainEvent):
    """Event emitted when LLM plan generation completes successfully."""

    user_prompt: str = ""
    generated_steps_count: int = 0
    latency_ms: float = 0.0


@dataclass
class ReasoningFailedEvent(DomainEvent):
    """Event emitted when LLM plan generation or validation fails."""

    user_prompt: str = ""
    reason: str = ""
    fallback_used: bool = True
