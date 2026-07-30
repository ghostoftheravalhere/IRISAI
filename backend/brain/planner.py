"""Planner stub for future intent-to-action planning."""

from __future__ import annotations

from dataclasses import dataclass

from backend.core.contracts.action import ActionRequest, ActionType
from backend.core.contracts.intent import Intent


@dataclass(frozen=True)
class Plan:
    """Placeholder action plan."""

    actions: tuple[ActionRequest, ...]


class Planner:
    """Pass-through planner with no business or AI logic."""

    def plan(self, intent: Intent) -> Plan:
        """Wrap an intent in a no-op action request for future execution."""
        return Plan(
            actions=(
                ActionRequest(
                    action_type=ActionType.NO_ACTION,
                    name=intent.name,
                    payload=dict(intent.payload),
                ),
            )
        )
