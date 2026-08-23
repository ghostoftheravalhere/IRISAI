"""Action Verification Domain Events."""

from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass(frozen=True)
class VerificationStartedEvent:
    """Emitted when action verification starts."""

    action_name: str
    verification_type: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class VerificationPassedEvent:
    """Emitted when action verification passes."""

    action_name: str
    confidence: float
    elapsed_time: float
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class VerificationFailedEvent:
    """Emitted when action verification fails."""

    action_name: str
    reason: str
    retry_count: int
    timestamp: float = field(default_factory=time.time)
