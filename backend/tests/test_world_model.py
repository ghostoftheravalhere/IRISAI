"""Unit tests for Desktop World Model & Universal Context Understanding Subsystem."""

from __future__ import annotations

from backend.context.world_model import DesktopWorldState, WorldModel, get_world_model_metrics
from backend.dialogue.conversation_session import ConversationSession
from backend.dialogue.reference_resolver import ReferenceResolver


def test_world_model_state_updates_and_history():
    wm = WorldModel()

    st1 = DesktopWorldState(active_application="Chrome", active_window="Google Search")
    wm.update_state(st1)

    assert wm.current_state.active_application == "Chrome"
    assert len(wm.get_history()) == 1

    st2 = DesktopWorldState(active_application="VS Code", active_window="app.py")
    wm.update_state(st2)

    assert wm.current_state.active_application == "VS Code"
    assert len(wm.get_history()) == 2

    metrics = get_world_model_metrics()
    assert metrics["total_updates"] >= 2
    assert metrics["state_changes_detected"] >= 1


def test_reference_resolver_with_world_state():
    wm = WorldModel()
    resolver = ReferenceResolver(world_model=wm)
    session = ConversationSession()

    st = DesktopWorldState(
        active_application="Chrome",
        visible_documents=["ResearchPaper.pdf"],
        selected_text="Machine Learning Overview",
        visible_dialogs=["Save Changes Confirmation"],
        visible_browser_tabs=["Tab 1", "Tab 2"],
    )
    wm.update_state(st)

    # Test "Summarize this" -> selected text / document
    resolved_text, target, query = resolver.resolve("Summarize this", session)
    assert query == "Machine Learning Overview"

    # Test "Close it" -> dialog
    resolved_text, target, query = resolver.resolve("Close it", session)
    assert target == "Save Changes Confirmation"

    # Test "Open the second one" -> second browser tab
    resolved_text, target, query = resolver.resolve("Open the second one", session)
    assert query == "Tab 2"
