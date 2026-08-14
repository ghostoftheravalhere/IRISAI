"""Action Verification Models & Policies."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any


@dataclass
class ActionVerificationPolicy:
    """Policy defining verification conditions for an action."""

    verification_type: str  # "OPEN_APPLICATION", "CLICK_VISUAL_TEXT", "TYPE_TEXT", "SEARCH_BROWSER", "RUN_TESTS", "SCROLL", "PRESS_KEY"
    timeout_sec: float = 3.0
    retry_count: int = 3
    success_conditions: list[str] = field(default_factory=list)
    failure_conditions: list[str] = field(default_factory=list)


@dataclass
class VerificationResult:
    """Outcome of an action verification evaluation."""

    success: bool
    confidence: float = 1.0
    reason: str = "Action verified successfully"
    elapsed_time: float = 0.0
    retry_count: int = 0
    verification_artifacts: dict[str, Any] = field(default_factory=dict)
