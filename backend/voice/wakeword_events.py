"""Wake Word & Natural Voice Domain Events."""

from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass(frozen=True)
class WakeWordDetectedEvent:
    """Event emitted when wake word is detected."""

    keyword: str = "Hey IRIS"
    confidence: float = 0.95
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class WakeWordTimeoutEvent:
    """Event emitted when voice listening times out with no speech input."""

    elapsed_sec: float
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class SpeechStartedEvent:
    """Event emitted when Text-to-Speech output begins."""

    text: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class SpeechCompletedEvent:
    """Event emitted when Text-to-Speech output finishes."""

    duration_ms: float
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class SpeechInterruptedEvent:
    """Event emitted when user interrupts active speech output."""

    reason: str = "user_stop"
    timestamp: float = field(default_factory=time.time)
