"""Dialogue Manager Data Models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any
import uuid


class DialogueState(str, Enum):
    """Dialogue session state."""

    IDLE = "IDLE"
    AWAITING_INPUT = "AWAITING_INPUT"
    AWAITING_CLARIFICATION = "AWAITING_CLARIFICATION"
    EXECUTING_WORKFLOW = "EXECUTING_WORKFLOW"


class DialoguePolicyAction(str, Enum):
    """Decision action from ConversationPolicy."""

    DIRECT_EXECUTION = "DIRECT_EXECUTION"
    CLARIFY = "CLARIFY"
    CONFIRM = "CONFIRM"


@dataclass
class FocusStackItem:
    """Entity or target currently on the conversational focus stack."""

    entity_type: str  # "app", "query", "url", "file", "ui_element"
    value: str
    turn_index: int
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DialogueTurn:
    """Individual conversational turn."""

    speaker: str  # "user" or "iris"
    raw_text: str
    turn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parsed_intent: str | None = None
    resolved_target: str | None = None
    resolved_query: str | None = None
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class ClarificationOption:
    """Option presented to user for clarifying ambiguous intent."""

    option_id: str
    label: str
    target_intent: str
    resolved_params: dict[str, Any] = field(default_factory=dict)
