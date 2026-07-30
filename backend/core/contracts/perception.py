"""Perception contracts for camera, microphone, and future sensors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class Frame:
    """Generic camera frame container."""

    data: Any
    captured_at: float | None = None


@dataclass(frozen=True)
class AudioChunk:
    """Generic microphone audio chunk container."""

    samples: Any
    sample_rate: int
    captured_at: float | None = None


@runtime_checkable
class PerceptionProvider(Protocol):
    """Protocol for raw sensor providers."""

    def start(self) -> object:
        """Start perception capture."""

    def stop(self) -> object:
        """Stop perception capture."""
