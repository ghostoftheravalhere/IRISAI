"""Unit tests for Canonical ActionEngine and ActionRequest data contracts."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from backend.automation.action_engine import ActionEngine
from backend.automation.action_models import ActionRequest, CanonicalAction
from backend.voice.command_parser import VoiceIntent, VoiceIntentType


@pytest.fixture
def mock_controller():
    controller = MagicMock()
    controller.open_application.return_value = True
    controller.close_window.return_value = True
    controller.click.return_value = True
    controller.hotkey.return_value = True
    controller.type_text.return_value = True
    controller.press.return_value = True
    return controller


def test_canonical_action_values():
    assert CanonicalAction.CLICK == "CLICK"
    assert CanonicalAction.OPEN_APPLICATION == "OPEN_APPLICATION"
    assert CanonicalAction.COPY == "COPY"


def test_action_engine_from_voice_intent():
    voice_intent = VoiceIntent(
        intent=VoiceIntentType.OPEN_APPLICATION,
        text="Open Chrome",
        target="chrome",
        confidence=0.95,
    )
    req = ActionEngine.from_voice_intent(voice_intent)
    assert req.action == CanonicalAction.OPEN_APPLICATION
    assert req.target_phrase == "chrome"
    assert req.confidence == 0.95


def test_action_engine_execute_open_application(mock_controller):
    engine = ActionEngine(mock_controller)
    req = ActionRequest(action=CanonicalAction.OPEN_APPLICATION, target_phrase="notepad")
    res = engine.execute(req)
    assert res.success is True
    assert "Notepad opened" in res.message
    mock_controller.open_application.assert_called_once_with("notepad")


def test_action_engine_execute_spatial_click(mock_controller):
    engine = ActionEngine(mock_controller)
    req = ActionRequest(action=CanonicalAction.RIGHT_CLICK, target_x=500.0, target_y=300.0)
    res = engine.execute(req)
    assert res.success is True
    mock_controller.move_rel.assert_called_once_with(500, 300)
    mock_controller.click.assert_called_once_with(button="right", clicks=1)


def test_action_engine_execute_copy_paste(mock_controller):
    engine = ActionEngine(mock_controller)
    res_copy = engine.execute(ActionRequest(action=CanonicalAction.COPY))
    res_paste = engine.execute(ActionRequest(action=CanonicalAction.PASTE))
    assert res_copy.success is True
    assert res_paste.success is True
    assert mock_controller.hotkey.call_count == 2
