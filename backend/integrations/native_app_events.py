"""Native Application Domain Events."""

from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass(frozen=True)
class NativeAppInvokedEvent:
    """Event emitted when a native app integration action is invoked."""

    app_name: str
    action: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class NativeAppExecutedEvent:
    """Event emitted when a native app integration action completes."""

    app_name: str
    action: str
    success: bool
    timestamp: float = field(default_factory=time.time)
