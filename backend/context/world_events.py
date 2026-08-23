"""World Model & Continuous Context Observer Events."""

from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass(frozen=True)
class WorldStateChangedEvent:
    """Emitted when live DesktopWorldState is updated."""

    active_app: str
    active_window: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class WindowChangedEvent:
    """Emitted when active foreground window title or HWND changes."""

    window_title: str
    app_name: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ApplicationOpenedEvent:
    """Emitted when a new application executable launches."""

    app_name: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ApplicationClosedEvent:
    """Emitted when an application process terminates."""

    app_name: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ClipboardChangedEvent:
    """Emitted when clipboard text changes."""

    clipboard_text: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class NotificationAppearedEvent:
    """Emitted when an OS toast notification emerges."""

    notification_title: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class BrowserNavigationEvent:
    """Emitted when active browser tab navigates to a new URL."""

    url: str
    page_title: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class DocumentChangedEvent:
    """Emitted when active editor file or cursor position changes."""

    file_path: str
    cursor_line: int
    timestamp: float = field(default_factory=time.time)
