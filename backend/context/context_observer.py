"""Continuous Context Observer & User Activity Inference Service."""

from __future__ import annotations

from threading import RLock
import time
from typing import Any

from backend.context.world_events import (
    ApplicationClosedEvent,
    ApplicationOpenedEvent,
    BrowserNavigationEvent,
    ClipboardChangedEvent,
    DocumentChangedEvent,
    NotificationAppearedEvent,
    WindowChangedEvent,
    WorldStateChangedEvent,
)
from backend.context.world_model import DesktopWorldState, WorldModel
from backend.core.events.bus import EventBus
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def infer_user_activity(state: DesktopWorldState) -> str:
    """Determine current user activity from desktop world state signals."""
    app_lower = state.active_application.lower()
    win_lower = state.active_window.lower()

    if "code" in app_lower or "devenv" in app_lower or "pycharm" in app_lower or "terminal" in app_lower or "idea" in app_lower:
        return "Coding"
    elif "chrome" in app_lower or "edge" in app_lower or "firefox" in app_lower or "brave" in app_lower:
        if "youtube" in win_lower or "netflix" in win_lower or state.audio_playing:
            return "Watching video"
        elif "github" in win_lower or "docs" in win_lower or "arxiv" in win_lower:
            return "Reading"
        return "Browsing"
    elif "zoom" in app_lower or "teams" in app_lower or "meet" in app_lower or "slack" in app_lower:
        return "Meeting"
    elif "steam" in app_lower or "game" in app_lower:
        return "Gaming"
    elif "word" in app_lower or "notepad" in app_lower or "obsidian" in app_lower:
        return "Writing"
    elif app_lower in ("system", "desktop", "idle"):
        return "Idle"
    return "Studying"


class ContextObserver:
    """Continuous event-driven observer updating WorldModel and inferring user activity without polling spam."""

    def __init__(self, world_model: WorldModel, event_bus: EventBus | None = None) -> None:
        self._world_model = world_model
        self._event_bus = event_bus
        self._lock = RLock()
        if self._event_bus:
            self._subscribe_events()

    def _subscribe_events(self) -> None:
        """Subscribe to desktop context domain events."""
        if not self._event_bus:
            return
        self._event_bus.subscribe(WindowChangedEvent, self._on_window_changed)
        self._event_bus.subscribe(ClipboardChangedEvent, self._on_clipboard_changed)
        self._event_bus.subscribe(BrowserNavigationEvent, self._on_browser_navigation)
        self._event_bus.subscribe(DocumentChangedEvent, self._on_document_changed)

    def _on_window_changed(self, event: WindowChangedEvent) -> None:
        with self._lock:
            curr = self._world_model.current_state
            activity = infer_user_activity(curr)
            new_st = DesktopWorldState(
                active_application=event.app_name,
                active_window=event.window_title,
                visible_documents=curr.visible_documents,
                visible_browser_tabs=curr.visible_browser_tabs,
                selected_text=curr.selected_text,
                clipboard=curr.clipboard,
                focused_control=curr.focused_control,
                visible_dialogs=curr.visible_dialogs,
                notifications=curr.notifications,
                current_url=curr.current_url,
                page_title=curr.page_title,
                current_project=curr.current_project,
                current_file=curr.current_file,
                cursor_line=curr.cursor_line,
                audio_playing=curr.audio_playing,
                inferred_activity=activity,
            )
            self._world_model.update_state(new_st)

    def _on_clipboard_changed(self, event: ClipboardChangedEvent) -> None:
        with self._lock:
            curr = self._world_model.current_state
            curr.clipboard = event.clipboard_text
            self._world_model.update_state(curr)

    def _on_browser_navigation(self, event: BrowserNavigationEvent) -> None:
        with self._lock:
            curr = self._world_model.current_state
            curr.current_url = event.url
            curr.page_title = event.page_title
            curr.inferred_activity = infer_user_activity(curr)
            self._world_model.update_state(curr)

    def _on_document_changed(self, event: DocumentChangedEvent) -> None:
        with self._lock:
            curr = self._world_model.current_state
            curr.current_file = event.file_path
            curr.cursor_line = event.cursor_line
            curr.inferred_activity = infer_user_activity(curr)
            self._world_model.update_state(curr)
