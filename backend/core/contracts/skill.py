"""Skill protocol for future domain capability modules."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.core.contracts.action import ActionRequest, ActionResult


@runtime_checkable
class Skill(Protocol):
    """Protocol implemented by domain-specific capabilities."""

    name: str

    def can_handle(self, request: ActionRequest) -> bool:
        """Return whether this skill can handle the request."""

    def execute(self, request: ActionRequest) -> ActionResult:
        """Execute the request and return an action result."""
