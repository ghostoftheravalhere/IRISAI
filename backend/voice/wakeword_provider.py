"""Pluggable Wake Word Provider Interface & Implementations."""

from __future__ import annotations

from typing import Any, Protocol, Sequence

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class WakeWordProvider(Protocol):
    """Protocol interface for offline wake word detection engines."""

    @property
    def name(self) -> str:
        ...

    def detect(self, audio_chunk: Any, sensitivity: float = 0.5) -> tuple[bool, str, float]:
        """Detect wake word in audio frame; returns (detected, keyword, confidence)."""
        ...


class MockWakeWordProvider:
    """Lightweight mock wake word provider for testing and environments without native binaries."""

    def __init__(self, keyword: str = "Hey IRIS") -> None:
        self._keyword = keyword

    @property
    def name(self) -> str:
        return "MockWakeWordProvider"

    def detect(self, audio_chunk: Any, sensitivity: float = 0.5) -> tuple[bool, str, float]:
        """Return True if chunk has synthetic trigger flag, else False."""
        if isinstance(audio_chunk, dict) and audio_chunk.get("trigger_wake_word"):
            return True, self._keyword, 0.98
        return False, "", 0.0


class OpenWakeWordProvider:
    """Local offline OpenWakeWord ONNX provider."""

    def __init__(self, keyword: str = "Hey IRIS") -> None:
        self._keyword = keyword

    @property
    def name(self) -> str:
        return "OpenWakeWordProvider"

    def detect(self, audio_chunk: Any, sensitivity: float = 0.5) -> tuple[bool, str, float]:
        # Fallback offline simulation
        return False, "", 0.0
