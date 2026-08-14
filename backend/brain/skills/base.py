"""Base data models and protocol interface for the Plugin & Skill Framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class SkillDescriptor:
    """Self-describing metadata for a registered Skill capability."""

    skill_id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    required_permissions: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SkillExecutionContext:
    """Encapsulates parameters and permissions for a skill invocation."""

    intent: str
    params: dict[str, Any] = field(default_factory=dict)
    session_id: str = "default"
    user_permissions: list[str] = field(default_factory=list)
    raw_transcript: str = ""


@dataclass(frozen=True)
class SkillResult:
    """Unified result model returned by a Skill execution."""

    success: bool
    message: str
    result_data: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None


class Skill(Protocol):
    """Protocol interface defining abstract Skill capabilities."""

    @property
    def descriptor(self) -> SkillDescriptor:
        """Return the Skill self-describing metadata descriptor."""
        ...

    def can_execute(self, context: SkillExecutionContext) -> tuple[bool, str]:
        """Validate whether the skill can execute the requested context."""
        ...

    def execute(self, context: SkillExecutionContext) -> SkillResult:
        """Execute the skill capability for the given context."""
        ...
