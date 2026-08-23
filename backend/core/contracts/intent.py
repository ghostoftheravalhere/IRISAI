"""Intent contracts for the IRIS AI V2 pipeline foundation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class IntentSource(str, Enum):
    """Supported sources that can produce an intent."""

    EYE = "eye"
    VOICE = "voice"
    SYSTEM = "system"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Confidence:
    """Normalized confidence value for interpreted intent data."""

    value: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError("confidence value must be in [0.0, 1.0].")


@runtime_checkable
class Intent(Protocol):
    """Protocol for unified intent objects from any input modality."""

    name: str
    source: IntentSource
    confidence: Confidence
    payload: dict[str, Any]
