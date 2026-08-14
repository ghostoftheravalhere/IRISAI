"""Domain events emitted during Skill framework discovery and execution."""

from __future__ import annotations

from dataclasses import dataclass

from backend.core.events.bus import DomainEvent


@dataclass
class SkillRegisteredEvent(DomainEvent):
    """Event emitted when a skill is registered with the SkillRegistry."""

    skill_id: str = ""
    name: str = ""
    version: str = "1.0.0"


@dataclass
class SkillExecutionStartedEvent(DomainEvent):
    """Event emitted when a skill execution context begins."""

    skill_id: str = ""
    intent: str = ""
    session_id: str = "default"


@dataclass
class SkillExecutionCompletedEvent(DomainEvent):
    """Event emitted when a skill execution finishes successfully."""

    skill_id: str = ""
    intent: str = ""
    success: bool = True
    execution_time_ms: float = 0.0


@dataclass
class SkillExecutionFailedEvent(DomainEvent):
    """Event emitted when a skill execution fails or is rejected by permission validation."""

    skill_id: str = ""
    intent: str = ""
    reason: str = ""
