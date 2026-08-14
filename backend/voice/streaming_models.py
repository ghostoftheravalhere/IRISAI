"""Streaming Intelligence & Interruptible Conversation Data Models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any


class StreamingPlannerAction(str, Enum):
    """Actions performed by the StreamingPlanner on active workflows."""

    REPLACE_PLAN = "REPLACE_PLAN"
    APPEND_STEPS = "APPEND_STEPS"
    CANCEL_STEPS = "CANCEL_STEPS"
    MERGE_PLAN = "MERGE_PLAN"


@dataclass
class StreamingTranscript:
    """Real-time streaming transcript frame."""

    text: str
    is_final: bool = False
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class PartialIntent:
    """Predictive partial intent model before utterance completion."""

    intent_name: str
    target: str | None = None
    query: str | None = None
    confidence: float = 0.80
    is_stable: bool = False
