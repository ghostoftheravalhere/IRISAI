"""Action contracts for the IRIS AI V2 pipeline foundation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class ActionType(str, Enum):
    """Generic action categories used by future unified action execution."""

    DESKTOP = "desktop"
    CURSOR = "cursor"
    SYSTEM = "system"
    NO_ACTION = "no_action"


@dataclass(frozen=True)
class ActionRequest:
    """Requested action produced by planning."""

    action_type: ActionType
    name: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionResult:
    """Result returned after action validation and execution."""

    success: bool
    action_type: ActionType
    message: str
    payload: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ActionExecutor(Protocol):
    """Protocol for components that can execute an action request."""

    def execute(self, request: ActionRequest) -> ActionResult:
        """Execute an action request and return its result."""
