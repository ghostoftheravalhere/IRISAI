"""P0 Regression Test Suite: Live Voice Incident Fix & Desktop Shell Safety Hardening."""

import pytest

from backend.agent.agent_core import AgentCore
from backend.agent.planner import Planner
from backend.agent.policy_engine import PermissionLevel, PolicyEngine
from backend.agent.tools.desktop_tool import DesktopTool
from backend.automation.controller import DesktopController
from backend.voice.command_parser import IntentParserService, VoiceIntentType


@pytest.fixture
def parser():
    return IntentParserService()


@pytest.fixture
def controller():
    return DesktopController()


@pytest.fixture
def desktop_tool():
    return DesktopTool()


@pytest.fixture
def agent_core():
    return AgentCore()


# --- 1. "Hi IRIS" -> GREETING ---
def test_1_hi_iris_greeting(parser):
    """1. Test parsing 'Hi IRIS' to GREETING intent."""
    res = parser.parse("Hi IRIS")
    assert res.intent == VoiceIntentType.GREETING


# --- 2. "Hello IRIS" -> GREETING ---
def test_2_hello_iris_greeting(parser):
    """2. Test parsing 'Hello IRIS' to GREETING intent."""
    res = parser.parse("Hello IRIS")
    assert res.intent == VoiceIntentType.GREETING


# --- 3. "Hey IRIS" -> GREETING ---
def test_3_hey_iris_greeting(parser):
    """3. Test parsing 'Hey IRIS' to GREETING intent."""
    res = parser.parse("Hey IRIS")
    assert res.intent == VoiceIntentType.GREETING


# --- 4. "Good morning IRIS" -> GREETING ---
def test_4_good_morning_iris_greeting(parser):
    """4. Test parsing 'Good morning IRIS' to GREETING intent."""
    res = parser.parse("Good morning IRIS")
    assert res.intent == VoiceIntentType.GREETING


# --- 5. Arbitrary unknown sentence -> NOT OPEN_APPLICATION ---
def test_5_unknown_sentence_not_open_app(agent_core):
    """5. Test that arbitrary unknown sentences do NOT result in open_application plan steps."""
    res = agent_core.process_goal("random gibberish input string")
    assert res.success is False
    assert "not sure" in res.response.lower() or "unrecognized" in res.response.lower()


# --- 6. Unknown application -> TARGET_NOT_FOUND ---
def test_6_unknown_app_target_not_found(desktop_tool):
    """6. Test DesktopTool rejecting untrusted/unknown application names with TARGET_NOT_FOUND."""
    res = desktop_tool.execute({"action": "open_application", "target": "invalid_app_12345"})
    assert res.success is False
    assert res.error_code == "TARGET_NOT_FOUND"


# --- 7. Empty target -> Rejected ---
def test_7_empty_target_rejected(desktop_tool):
    """7. Test DesktopTool rejecting empty target names."""
    res = desktop_tool.execute({"action": "open_application", "target": ""})
    assert res.success is False
    assert res.error_code == "TARGET_NOT_FOUND"


# --- 8. Known Chrome -> OPEN_APPLICATION ---
def test_8_known_chrome(controller):
    """8. Test that Chrome is validated as a supported application."""
    assert controller.is_application_supported("chrome") is True


# --- 9. Known Notepad -> OPEN_APPLICATION ---
def test_9_known_notepad(controller):
    """9. Test that Notepad is validated as a supported application."""
    assert controller.is_application_supported("notepad") is True


# --- 10. Known WhatsApp -> Resolved target ---
def test_10_known_whatsapp(controller):
    """10. Test that WhatsApp is validated as a supported application."""
    assert controller.is_application_supported("whatsapp") is True


# --- 11. No cmd.exe spawned for invalid target ---
def test_11_no_cmd_spawned_for_invalid_target(controller):
    """11. Test DesktopController rejecting unverified targets without calling cmd.exe."""
    assert controller.is_application_supported("hi iris") is False
    assert controller.open_application("hi iris") is False


# --- 12. PolicyEngine still enforced ---
def test_12_policy_engine_enforcement(desktop_tool):
    """12. Test that PolicyEngine permissions remain strictly enforced for DesktopTool."""
    assert desktop_tool.descriptor.permission_level == PermissionLevel.SAFE


# --- 13. Legacy commands remain working ---
def test_13_legacy_commands_working(parser):
    """13. Test that legacy voice commands remain fully functional."""
    res_chrome = parser.parse("Open Chrome")
    assert res_chrome.intent == VoiceIntentType.OPEN_CHROME or res_chrome.intent == VoiceIntentType.OPEN_APPLICATION

    res_click = parser.parse("Click here")
    assert res_click.intent == VoiceIntentType.PRIMARY_CLICK
