"""Autonomous Agent Runtime Data Models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any
import uuid


class AgentLoopPhase(str, Enum):
    """Execution loop phases for autonomous agents."""

    OBSERVE = "OBSERVE"
    REASON = "REASON"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    VERIFY = "VERIFY"
    REFLECT = "REFLECT"
    RECOVER = "RECOVER"
    FINISHED = "FINISHED"


@dataclass
class AgentObservation:
    """Multimodal observation snapshot prior to planning cycle."""

    active_app: str
    visible_text: str
    dialogue_state: str
    memory_summary: str
    workspace_name: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class ReflectionReport:
    """Outcome of post-action reflection evaluation."""

    step_name: str
    success: bool
    delta_observed: bool
    continue_plan: bool
    suggested_replan: bool = False
    notes: str = ""
    timestamp: float = field(default_factory=time.time)
