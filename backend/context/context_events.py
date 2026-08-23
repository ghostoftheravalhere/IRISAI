"""Desktop Context Domain Events."""

from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass(frozen=True)
class DesktopContextChangedEvent:
    """Emitted when overall desktop world state updates."""

    active_app: str
    active_window: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ApplicationChangedEvent:
    """Emitted when active application switches."""

    previous_app: str
    current_app: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class SelectionChangedEvent:
    """Emitted when text selection changes."""

    selected_text: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class DialogAppearedEvent:
    """Emitted when a modal dialog or popup emerges."""

    dialog_title: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ClipboardChangedEvent:
    """Emitted when clipboard content changes."""

    clipboard_text: str
    timestamp: float = field(default_factory=time.time)
