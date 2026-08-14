"""Unit tests for Live Desktop World Model & Continuous Context Observer Subsystem."""

from __future__ import annotations

from backend.context.context_observer import ContextObserver, infer_user_activity
from backend.context.world_events import (
    BrowserNavigationEvent,
    ClipboardChangedEvent,
    DocumentChangedEvent,
    WindowChangedEvent,
)
from backend.context.world_model import DesktopWorldState, WorldModel
from backend.core.events.bus import EventBus


def test_user_activity_inference():
    st_coding = DesktopWorldState(active_application="Code.exe", active_window="app.py - IRISAI")
    assert infer_user_activity(st_coding) == "Coding"

    st_browsing = DesktopWorldState(active_application="chrome.exe", active_window="Google Search")
    assert infer_user_activity(st_browsing) == "Browsing"

    st_video = DesktopWorldState(active_application="chrome.exe", active_window="YouTube - Video Player", audio_playing=True)
    assert infer_user_activity(st_video) == "Watching video"

    st_meeting = DesktopWorldState(active_application="Zoom.exe", active_window="Team Sync")
    assert infer_user_activity(st_meeting) == "Meeting"


def test_context_observer_event_propagation():
    bus = EventBus()
    wm = WorldModel(event_bus=bus)
    observer = ContextObserver(world_model=wm, event_bus=bus)

    bus.publish(WindowChangedEvent(window_title="GitHub - Pytest", app_name="chrome.exe"))
    assert wm.current_state.active_application == "chrome.exe"

    bus.publish(BrowserNavigationEvent(url="https://github.com", page_title="GitHub Repository"))
    assert wm.current_state.current_url == "https://github.com"
    assert wm.current_state.page_title == "GitHub Repository"

    bus.publish(ClipboardChangedEvent(clipboard_text="Sample copied text"))
    assert wm.current_state.clipboard == "Sample copied text"

    bus.publish(DocumentChangedEvent(file_path="main.py", cursor_line=42))
    assert wm.current_state.current_file == "main.py"
    assert wm.current_state.cursor_line == 42
