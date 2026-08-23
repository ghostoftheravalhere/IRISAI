"""Adaptive Learning & Personalization Engine Data Models."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any
import uuid


@dataclass
class BehavioralSignal:
    """Anonymized interaction signal model."""

    signal_type: str  # "app_launch", "test_run", "command_freq", "voice_freq"
    target: str
    hour_of_day: int = 20
    day_of_week: int = 1
    duration_sec: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class DetectedRoutine:
    """Discovered recurring temporal routine model."""

    name: str
    trigger_time: str  # e.g., "Weekdays 20:00"
    sequence_apps: list[str] = field(default_factory=list)
    confidence: float = 0.85
    occurrence_count: int = 5
    routine_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class UserPreferences:
    """Learned user preferences model."""

    preferred_browser: str = "chrome"
    preferred_ide: str = "vscode"
    preferred_music_app: str = "spotify"
    response_length: str = "concise"  # "concise" or "detailed"
    learning_enabled: bool = True
    suggestion_frequency: str = "medium"  # "low", "medium", "high"


@dataclass
class ProactiveSuggestion:
    """Non-intrusive dismissible suggestion model."""

    prompt_text: str
    suggested_action: str
    confidence: float = 0.85
    dismissed: bool = False
    suggestion_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
