"""Comprehensive End-to-End Runtime Integration Tests for Conversational Accessibility Agent.

Exercises the actual AppContainer composition root, VoiceCommandPipeline, BrainOrchestrator,
MultimodalFusionEngine, DialogueManager, AmbiguityEngine, SelectionManager, and ActionEngine.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch
import pytest

from backend.automation.action_models import ActionRequest, ActionResult, CanonicalAction
from backend.automation.controller import DesktopController
from backend.brain.fusion import PerceptionEvent
from backend.config.settings import Settings
from backend.core.di.container import build_container
from backend.eye_tracking.gaze_service import GazeEstimate
from backend.perception.ambiguity_engine import CandidateMatch
from backend.voice.command_parser import VoiceIntentType


@pytest.fixture
def test_container():
    """Build real container instance with mocked OS execution calls in DesktopController."""
    settings = Settings(
        APP_ENV="testing",
        BRAIN_ORCHESTRATOR_ENABLED=True,
        FUSION_ENGINE_ENABLED=True,
    )
    container = build_container(settings)

    mock_click = MagicMock(return_value=True)
    mock_hotkey = MagicMock(return_value=True)
    mock_open_app = MagicMock(return_value=True)
    mock_close_win = MagicMock(return_value=True)
    mock_close_app = MagicMock(return_value=ActionResult(True, CanonicalAction.CLOSE_APPLICATION, "Closed"))
    mock_scroll = MagicMock(return_value=True)
    mock_press = MagicMock(return_value=True)
    mock_type_text = MagicMock(return_value=True)
    mock_move_rel = MagicMock(return_value=True)

    for ctrl in (container.desktop_controller, container.canonical_action_engine._desktop_controller):
        ctrl.click = mock_click
        ctrl.hotkey = mock_hotkey
        ctrl.open_application = mock_open_app
        ctrl.close_window = mock_close_win
        ctrl.close_application = mock_close_app
        ctrl.scroll = mock_scroll
        ctrl.press = mock_press
        ctrl.type_text = mock_type_text
        ctrl.move_rel = mock_move_rel

    return container


def test_integration_right_click(test_container):
    """1. Right click through real voice parser path."""
    res = test_container.voice_pipeline.execute("Right click")
    assert res.success is True
    assert res.intent == VoiceIntentType.RIGHT_CLICK.value
    test_container.desktop_controller.click.assert_called_with(button="right", clicks=1)


def test_integration_double_click(test_container):
    """2. Double click through real voice parser path."""
    res = test_container.voice_pipeline.execute("Double click")
    assert res.success is True
    assert res.intent == VoiceIntentType.DOUBLE_CLICK.value
    test_container.desktop_controller.click.assert_called_with(button="left", clicks=2)


def test_integration_start_and_stop_selecting(test_container):
    """3 & 4. Start selecting and Stop selecting through real pipeline."""
    res_start = test_container.voice_pipeline.execute("Start selecting")
    assert res_start.success is True
    assert test_container.selection_manager.get_state().is_selecting is True

    res_stop = test_container.voice_pipeline.execute("Stop selecting")
    assert res_stop.success is True
    assert test_container.selection_manager.get_state().is_selecting is False


def test_integration_copy_it(test_container):
    """5. Copy it phrase command."""
    res = test_container.voice_pipeline.execute("Copy it")
    assert res.success is True
    test_container.desktop_controller.hotkey.assert_called_with("ctrl", "c")


def test_integration_open_chat(test_container):
    """6. Open chat command parsing."""
    res = test_container.voice_pipeline.execute("Open chat with Dev Nayi Clg")
    assert res.intent == VoiceIntentType.OPEN_CHAT.value or res.intent == VoiceIntentType.OPEN_APPLICATION.value


def test_integration_one_candidate_target(test_container):
    """7. Single candidate target execution."""
    c1 = CandidateMatch("Chrome", 100.0, 200.0, 0.95, "Exact match", "button")
    with patch.object(test_container.ambiguity_engine, "resolve_candidates") as mock_resolve:
        from backend.perception.ambiguity_engine import AmbiguityResolution
        mock_resolve.return_value = AmbiguityResolution("HIGH_CONFIDENCE", c1, (c1,))
        res = test_container.voice_pipeline.execute("Open Chrome")
        assert res.success is True
        test_container.desktop_controller.open_application.assert_called_once()


def test_integration_multi_candidate_and_ordinal_selection(test_container):
    """8, 13. Multi-candidate target triggers clarification prompt, followed by ordinal response."""
    c1 = CandidateMatch("Dev Nayi Clg", 100.0, 200.0, 0.70, "Fuzzy match", "chat")
    c2 = CandidateMatch("Dev Clg Group", 100.0, 250.0, 0.68, "Fuzzy match", "chat")

    with patch.object(test_container.ambiguity_engine, "resolve_candidates") as mock_resolve:
        from backend.perception.ambiguity_engine import AmbiguityResolution
        mock_resolve.return_value = AmbiguityResolution(
            "MULTIPLE_CANDIDATES",
            c1,
            (c1, c2),
            prompt_message="I found multiple matches: 1. Dev Nayi Clg, 2. Dev Clg Group. Which one?",
        )

        # Turn 1: Triggers clarification
        res1 = test_container.voice_pipeline.execute("Open Dev Clg")
        assert "multiple matches" in res1.message

        # Turn 2: User responds "Second one"
        res2 = test_container.voice_pipeline.execute("Second one")
        assert res2.success is True
        test_container.desktop_controller.open_application.assert_called_with("dev clg group")


def test_integration_confirmation_yes(test_container):
    """9, 10. Confirmation prompt followed by 'Yes' response."""
    c1 = CandidateMatch("Dev Nayi Clg", 100.0, 200.0, 0.75, "Fuzzy match", "chat")
    with patch.object(test_container.ambiguity_engine, "resolve_candidates") as mock_resolve:
        from backend.perception.ambiguity_engine import AmbiguityResolution
        mock_resolve.return_value = AmbiguityResolution(
            "MEDIUM_CONFIDENCE",
            c1,
            (c1,),
            prompt_message="I found Dev Nayi Clg. Do you want me to open it?",
        )

        res1 = test_container.voice_pipeline.execute("Open Dev Clg")
        assert "Dev Nayi Clg" in res1.message

        res2 = test_container.voice_pipeline.execute("Yes")
        assert res2.success is True
        test_container.desktop_controller.open_application.assert_called_with("dev nayi clg")


def test_integration_confirmation_no(test_container):
    """11. Confirmation prompt followed by 'No' response."""
    c1 = CandidateMatch("Dev Nayi Clg", 100.0, 200.0, 0.75, "Fuzzy match", "chat")
    with patch.object(test_container.ambiguity_engine, "resolve_candidates") as mock_resolve:
        from backend.perception.ambiguity_engine import AmbiguityResolution
        mock_resolve.return_value = AmbiguityResolution(
            "MEDIUM_CONFIDENCE",
            c1,
            (c1,),
            prompt_message="I found Dev Nayi Clg. Do you want me to open it?",
        )

        test_container.voice_pipeline.execute("Open Dev Clg")
        res2 = test_container.voice_pipeline.execute("No")
        assert res2.success is True
        assert "cancelled" in res2.message.lower()
        test_container.desktop_controller.open_application.assert_not_called()


def test_integration_cancellation(test_container):
    """12. Cancellation prompt via 'Cancel'."""
    c1 = CandidateMatch("Dev Nayi Clg", 100.0, 200.0, 0.75, "Fuzzy match", "chat")
    with patch.object(test_container.ambiguity_engine, "resolve_candidates") as mock_resolve:
        from backend.perception.ambiguity_engine import AmbiguityResolution
        mock_resolve.return_value = AmbiguityResolution(
            "MEDIUM_CONFIDENCE",
            c1,
            (c1,),
            prompt_message="I found Dev Nayi Clg. Do you want me to open it?",
        )

        test_container.voice_pipeline.execute("Open Dev Clg")
        res2 = test_container.voice_pipeline.execute("Cancel")
        assert res2.success is True
        assert "cancelled" in res2.message.lower()


def test_integration_gaze_right_click_here(test_container):
    """14. Gaze + 'Right click here' deictic spatial command."""
    from backend.eye_tracking.calibration import EyeCenter
    gaze = GazeEstimate(eye_center=EyeCenter(0.5, 0.5), raw_x=450.0, raw_y=350.0, x=450.0, y=350.0, confidence=0.92, captured_at=time.time())
    with patch.object(test_container.eye_gaze, "get_latest_gaze", return_value=gaze):
        pevent = PerceptionEvent(source="voice", intent="RIGHT_CLICK", confidence=1.0, raw_text="Right click here")
        fused = test_container.fusion_engine.ingest_event(pevent)
        assert fused is not None
        assert fused.unified_intent == "RIGHT_CLICK"

        orch_res = test_container.brain_orchestrator.process_fusion_result(fused)
        assert orch_res.success is True
        assert test_container.canonical_action_engine._desktop_controller.click.call_count >= 1


def test_integration_gaze_click_this(test_container):
    """15. Gaze + 'Click this' deictic spatial command."""
    from backend.eye_tracking.calibration import EyeCenter
    gaze = GazeEstimate(eye_center=EyeCenter(0.5, 0.5), raw_x=500.0, raw_y=600.0, x=500.0, y=600.0, confidence=0.88, captured_at=time.time())
    with patch.object(test_container.eye_gaze, "get_latest_gaze", return_value=gaze):
        pevent = PerceptionEvent(source="voice", intent="PRIMARY_CLICK", confidence=1.0, raw_text="Click this")
        fused = test_container.fusion_engine.ingest_event(pevent)
        assert fused is not None

        orch_res = test_container.brain_orchestrator.process_fusion_result(fused)
        assert orch_res.success is True
        assert test_container.canonical_action_engine._desktop_controller.click.call_count >= 1


def test_integration_low_confidence_gaze(test_container):
    """16. Low confidence gaze rejection."""
    from backend.eye_tracking.calibration import EyeCenter
    gaze = GazeEstimate(eye_center=EyeCenter(0.5, 0.5), raw_x=500.0, raw_y=600.0, x=500.0, y=600.0, confidence=0.20, captured_at=time.time())
    with patch.object(test_container.eye_gaze, "get_latest_gaze", return_value=gaze):
        pevent = PerceptionEvent(source="voice", intent="PRIMARY_CLICK", confidence=1.0, raw_text="Click this")
        fused = test_container.fusion_engine.ingest_event(pevent)
        assert fused.unified_intent == "TARGET_UNAVAILABLE"


def test_integration_stale_gaze(test_container):
    """17. Stale gaze rejection (>0.5s old)."""
    from backend.eye_tracking.calibration import EyeCenter
    gaze = GazeEstimate(eye_center=EyeCenter(0.5, 0.5), raw_x=500.0, raw_y=600.0, x=500.0, y=600.0, confidence=0.90, captured_at=time.time() - 2.0)
    with patch.object(test_container.eye_gaze, "get_latest_gaze", return_value=gaze):
        pevent = PerceptionEvent(source="voice", intent="PRIMARY_CLICK", confidence=1.0, raw_text="Click this")
        fused = test_container.fusion_engine.ingest_event(pevent)
        assert fused.unified_intent == "TARGET_UNAVAILABLE"


def test_integration_followup_command_context(test_container):
    """18. Follow-up command using context."""
    res1 = test_container.voice_pipeline.execute("Open Chrome")
    assert res1.success is True

    res2 = test_container.voice_pipeline.execute("Copy")
    assert res2.success is True


def test_integration_existing_simple_voice_commands(test_container):
    """19. Existing simple voice commands continue to function."""
    assert test_container.voice_pipeline.execute("Open Chrome").success is True
    assert test_container.voice_pipeline.execute("Open Notepad").success is True
    assert test_container.voice_pipeline.execute("Copy").success is True
    assert test_container.voice_pipeline.execute("Paste").success is True
    assert test_container.voice_pipeline.execute("Scroll down").success is True
    assert test_container.voice_pipeline.execute("Scroll up").success is True
    assert test_container.voice_pipeline.execute("Volume up").success is True
    assert test_container.voice_pipeline.execute("Volume down").success is True
    assert test_container.voice_pipeline.execute("Close window").success is True
    assert test_container.voice_pipeline.execute("Minimize window").success is True


def test_integration_no_duplicate_execution(test_container):
    """20. Verification that single voice turn produces exactly one action call."""
    test_container.desktop_controller.hotkey.reset_mock()
    test_container.voice_pipeline.execute("Copy")
    assert test_container.desktop_controller.hotkey.call_count == 1


# --- TASK-007 Natural Language Command Understanding Integration Tests ---

def test_task007_command_paraphrases(test_container):
    """1. Command paraphrases: 'Launch Chrome', 'Start Chrome', 'Can you open Chrome?'."""
    assert test_container.voice_pipeline.execute("Launch Chrome").success is True
    assert test_container.voice_pipeline.execute("Start Chrome").success is True
    assert test_container.voice_pipeline.execute("Can you open Chrome?").success is True


def test_task007_application_synonyms(test_container):
    """2. Application synonyms: 'Google Chrome', 'VS Code'."""
    res1 = test_container.voice_pipeline.execute("Open Google Chrome")
    assert res1.success is True
    assert res1.intent in {VoiceIntentType.OPEN_CHROME.value, VoiceIntentType.OPEN_APPLICATION.value}

    res2 = test_container.voice_pipeline.execute("Open VS Code")
    assert res2.success is True


def test_task007_target_extraction(test_container):
    """3. Target extraction: 'Open my Dev Clg chat', 'Go to Dev Nayi Clg', 'Take me to Dev Nayi Clg'."""
    res1 = test_container.voice_pipeline.execute("Open my Dev Clg chat")
    assert res1.intent == VoiceIntentType.OPEN_CHAT.value or res1.intent == VoiceIntentType.OPEN_APPLICATION.value

    res2 = test_container.voice_pipeline.execute("Go to Dev Nayi Clg")
    assert res2.success is True

    res3 = test_container.voice_pipeline.execute("Take me to Dev Nayi Clg")
    assert res3.success is True


def test_task007_followup_command(test_container):
    """4. Follow-up command after target resolution."""
    test_container.voice_pipeline.execute("Open WhatsApp")
    res = test_container.voice_pipeline.execute("Type hello")
    assert res.success is True
    test_container.desktop_controller.type_text.assert_called_with("hello")


def test_task007_pronoun_it(test_container):
    """5. Referential pronoun 'it' ('Open Chrome' -> 'Close it')."""
    test_container.voice_pipeline.execute("Open Chrome")
    res = test_container.voice_pipeline.execute("Close it")
    assert res.success is True


def test_task007_pronoun_that(test_container):
    """6. Referential pronoun 'that' ('Copy that')."""
    res = test_container.voice_pipeline.execute("Copy that")
    assert res.success is True
    test_container.desktop_controller.hotkey.assert_called_with("ctrl", "c")


def test_task007_pronoun_this(test_container):
    """7. Referential pronoun 'this' ('Click this')."""
    from backend.eye_tracking.calibration import EyeCenter
    gaze = GazeEstimate(eye_center=EyeCenter(0.5, 0.5), raw_x=500.0, raw_y=600.0, x=500.0, y=600.0, confidence=0.88, captured_at=time.time())
    with patch.object(test_container.eye_gaze, "get_latest_gaze", return_value=gaze):
        pevent = PerceptionEvent(source="voice", intent="PRIMARY_CLICK", confidence=1.0, raw_text="Click this")
        fused = test_container.fusion_engine.ingest_event(pevent)
        assert fused is not None
        orch_res = test_container.brain_orchestrator.process_fusion_result(fused)
        assert orch_res.success is True


def test_task007_ordinal_clarification(test_container):
    """8. Ordinal clarification ('the second one', 'the first one')."""
    c1 = CandidateMatch("Dev Nayi Clg", 100.0, 200.0, 0.70, "Fuzzy match", "chat")
    c2 = CandidateMatch("Dev Clg Group", 100.0, 250.0, 0.68, "Fuzzy match", "chat")

    with patch.object(test_container.ambiguity_engine, "resolve_candidates") as mock_resolve:
        from backend.perception.ambiguity_engine import AmbiguityResolution
        mock_resolve.return_value = AmbiguityResolution(
            "MULTIPLE_CANDIDATES",
            c1,
            (c1, c2),
            prompt_message="1. Dev Nayi Clg 2. Dev Clg Group. Which one?",
        )
        test_container.voice_pipeline.execute("Open Dev Clg")
        res = test_container.voice_pipeline.execute("the first one")
        assert res.success is True
        test_container.desktop_controller.open_application.assert_called_with("dev nayi clg")


def test_task007_confirmation(test_container):
    """9. Confirmation prompt and 'Yes' response."""
    c1 = CandidateMatch("Dev Nayi Clg", 100.0, 200.0, 0.75, "Fuzzy match", "chat")
    with patch.object(test_container.ambiguity_engine, "resolve_candidates") as mock_resolve:
        from backend.perception.ambiguity_engine import AmbiguityResolution
        mock_resolve.return_value = AmbiguityResolution(
            "MEDIUM_CONFIDENCE", c1, (c1,), prompt_message="Open Dev Nayi Clg?"
        )
        test_container.voice_pipeline.execute("Open Dev Clg")
        res = test_container.voice_pipeline.execute("Yes")
        assert res.success is True


def test_task007_cancellation(test_container):
    """10. Cancellation response 'Cancel' or 'No'."""
    c1 = CandidateMatch("Dev Nayi Clg", 100.0, 200.0, 0.75, "Fuzzy match", "chat")
    with patch.object(test_container.ambiguity_engine, "resolve_candidates") as mock_resolve:
        from backend.perception.ambiguity_engine import AmbiguityResolution
        mock_resolve.return_value = AmbiguityResolution(
            "MEDIUM_CONFIDENCE", c1, (c1,), prompt_message="Open Dev Nayi Clg?"
        )
        test_container.voice_pipeline.execute("Open Dev Clg")
        res = test_container.voice_pipeline.execute("No")
        assert res.success is True
        assert "cancelled" in res.message.lower()


def test_task007_current_app_context(test_container):
    """11. Current app context preservation."""
    req = ActionRequest(action=CanonicalAction.OPEN_APPLICATION, target_phrase="chrome")
    res = test_container.dialogue_manager.process_utterance("Open Chrome", voice_request=req, active_app="chrome")
    assert res.executed_result.success is True
    assert test_container.dialogue_manager._last_active_app == "chrome"


def test_task007_current_chat_context(test_container):
    """12. Current chat context preservation."""
    res = test_container.voice_pipeline.execute("Open my Dev Clg chat")
    assert res.success is True
    assert test_container.dialogue_manager._last_resolved_target == "dev clg"


def test_task007_high_confidence_execution(test_container):
    """13. High confidence direct action execution without prompts."""
    res = test_container.voice_pipeline.execute("Open Chrome")
    assert res.success is True
    assert "open" in res.message.lower() or "chrome" in res.message.lower()


def test_task007_low_confidence_clarification(test_container):
    """14. Low/Medium confidence triggers clarification or confirmation prompt."""
    c1 = CandidateMatch("Dev Nayi Clg", 100.0, 200.0, 0.72, "Fuzzy match", "chat")
    with patch.object(test_container.ambiguity_engine, "resolve_candidates") as mock_resolve:
        from backend.perception.ambiguity_engine import AmbiguityResolution
        mock_resolve.return_value = AmbiguityResolution(
            "MEDIUM_CONFIDENCE", c1, (c1,), prompt_message="I found 'Dev Nayi Clg'. Open it?"
        )
        res = test_container.voice_pipeline.execute("Open Dev Clg")
        assert "Open it?" in res.message


def test_task007_existing_legacy_commands(test_container):
    """15. Existing legacy commands continue to function."""
    assert test_container.voice_pipeline.execute("Scroll down").success is True
    assert test_container.voice_pipeline.execute("Mute").success is True


def test_task007_copy_it(test_container):
    """16. Conversational 'Copy it' phrase."""
    res = test_container.voice_pipeline.execute("Copy it")
    assert res.success is True
    test_container.desktop_controller.hotkey.assert_called_with("ctrl", "c")


def test_task007_copy_this(test_container):
    """17. Conversational 'Copy this' phrase."""
    res = test_container.voice_pipeline.execute("Copy this")
    assert res.success is True
    test_container.desktop_controller.hotkey.assert_called_with("ctrl", "c")


def test_task007_paste_here(test_container):
    """18. Conversational 'Paste here' phrase."""
    res = test_container.voice_pipeline.execute("Paste here")
    assert res.success is True
    test_container.desktop_controller.hotkey.assert_called_with("ctrl", "v")


# --- App-Agnostic Architecture Verification Tests ---

def test_app_agnostic_unknown_target_resolution(test_container):
    """1. Unknown target ('Photoshop', 'Slack', 'Project Report') resolved dynamically without parser code."""
    res1 = test_container.voice_pipeline.execute("Open Photoshop")
    assert res1.success is True
    test_container.desktop_controller.open_application.assert_called_with("photoshop")

    res2 = test_container.voice_pipeline.execute("Open Slack")
    assert res2.success is True
    test_container.desktop_controller.open_application.assert_called_with("slack")

    res3 = test_container.voice_pipeline.execute("Open my Project Report document")
    assert res3.success is True
    test_container.desktop_controller.open_application.assert_called_with("project report")


def test_app_agnostic_new_app_open(test_container):
    """2. Any unlisted application is routed through OPEN_APPLICATION."""
    res = test_container.voice_pipeline.execute("Launch Figma")
    assert res.success is True
    assert res.intent in {VoiceIntentType.OPEN_APPLICATION.value, "OPEN_APPLICATION"}
    test_container.desktop_controller.open_application.assert_called_with("figma")


def test_app_agnostic_generic_ui_element_resolution(test_container):
    """3. Generic UI element ('Save button', 'New tab') resolved via AmbiguityEngine."""
    c1 = CandidateMatch("Save button", 200.0, 300.0, 0.90, "UIA match", "button")
    with patch.object(test_container.ambiguity_engine, "resolve_candidates") as mock_resolve:
        from backend.perception.ambiguity_engine import AmbiguityResolution
        mock_resolve.return_value = AmbiguityResolution("HIGH_CONFIDENCE", c1, (c1,))
        res = test_container.voice_pipeline.execute("Click Save button")
        assert res.success is True


def test_app_agnostic_generic_context_followup(test_container):
    """4. Generic context follow-up across applications (VSCode -> Type hello)."""
    test_container.voice_pipeline.execute("Open VS Code")
    res = test_container.voice_pipeline.execute("Type hello world")
    assert res.success is True
    test_container.desktop_controller.type_text.assert_called_with("hello world")


def test_app_agnostic_deictic_references(test_container):
    """5. Generic 'this/that/it/here' references across applications."""
    test_container.voice_pipeline.execute("Open Notepad")
    res = test_container.voice_pipeline.execute("Close it")
    assert res.success is True


def test_app_agnostic_copy_paste(test_container):
    """6. Copy/paste behavior is application-agnostic across arbitrary active apps."""
    test_container.voice_pipeline.execute("Open Excel")
    assert test_container.voice_pipeline.execute("Copy this").success is True
    assert test_container.voice_pipeline.execute("Paste here").success is True
    test_container.desktop_controller.hotkey.assert_called_with("ctrl", "v")


def test_app_agnostic_arbitrary_ambiguity_candidates(test_container):
    """7. Ambiguity logic works for arbitrary candidate names ('Project Alpha', 'Project Beta')."""
    c1 = CandidateMatch("Project Alpha", 100.0, 200.0, 0.70, "Fuzzy match", "document")
    c2 = CandidateMatch("Project Beta", 100.0, 250.0, 0.68, "Fuzzy match", "document")

    with patch.object(test_container.ambiguity_engine, "resolve_candidates") as mock_resolve:
        from backend.perception.ambiguity_engine import AmbiguityResolution
        mock_resolve.return_value = AmbiguityResolution(
            "MULTIPLE_CANDIDATES",
            c1,
            (c1, c2),
            prompt_message="1. Project Alpha 2. Project Beta. Which one?",
        )
        test_container.voice_pipeline.execute("Open Project")
        res = test_container.voice_pipeline.execute("Second one")
        assert res.success is True
        test_container.desktop_controller.open_application.assert_called_with("project beta")


# --- AgentCore Live Voice Integration Tests ---

def test_agent_core_voice_no_intent_routing(test_container):
    """1. Unmatched complex natural language prompts (NO_INTENT) route to AgentCore."""
    res = test_container.voice_pipeline.execute("IRIS, check my GitHub repository and tell me what we've completed")
    assert res.success is True
    assert res.intent == "AGENT_CORE"
    assert "repository" in res.message.lower() or "branch" in res.message.lower() or "completed" in res.message.lower()


def test_agent_core_voice_compound_command(test_container):
    """2. Compound multi-action requests ('Open Notepad and type hello') route to AgentCore."""
    res = test_container.voice_pipeline.execute("IRIS, open Notepad and type hello")
    assert res.success is True
    assert res.intent == "AGENT_CORE"


def test_agent_core_voice_browser_research(test_container):
    """3. Web research & summarization requests route to AgentCore."""
    res = test_container.voice_pipeline.execute("IRIS, search the web for Python 3.14 release information and summarize it")
    assert res.success is True
    assert res.intent == "AGENT_CORE"


def test_agent_core_voice_confirmation_bridge(test_container):
    """4. Action requiring confirmation pauses, prompts user, and resumes on 'yes'."""
    res1 = test_container.voice_pipeline.execute("IRIS, delete file old_report.txt")
    assert res1.intent == "AGENT_CORE"
    assert "confirm" in res1.message.lower() or "proceed" in res1.message.lower()

    # User confirms "yes"
    res2 = test_container.voice_pipeline.execute("yes")
    assert res2.success is True


def test_agent_core_legacy_command_optimization(test_container):
    """5. Simple legacy commands ('Open Chrome') bypass AgentCore and use optimized ActionEngine path."""
    res = test_container.voice_pipeline.execute("Open Chrome")
    assert res.success is True
    assert res.intent in {VoiceIntentType.OPEN_CHROME.value, "OPEN_CHROME", "OPEN_APPLICATION"}
    test_container.desktop_controller.open_application.assert_called_with("chrome")
