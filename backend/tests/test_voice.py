"""Voice recognition and intent parsing unit tests."""

from __future__ import annotations

from types import SimpleNamespace

from backend.automation.controller import ApplicationCloseResult, DesktopController
from backend.automation.dispatcher import AutomationDispatcher
from backend.voice.command_parser import IntentParserService, VoiceIntentType
from backend.voice.pipeline import VoiceCommandPipeline
from backend.voice.recognizer import ListenMode, VoiceRecognitionConfig, VoiceRecognitionService


class _FakeActionEngine:
    def __init__(self, cooldown_active: bool = False) -> None:
        self._cooldown_active = cooldown_active

    def get_latest_state(self):
        return SimpleNamespace(
            action=SimpleNamespace(value="NO_ACTION"),
            cooldownActive=self._cooldown_active,
            cursorPaused=False,
        )


class _FakeDesktop(DesktopController):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def open_chrome(self) -> bool:
        self.calls.append("open_chrome")
        return True

    def close_window(self) -> bool:
        self.calls.append("close_window")
        return True

    def close_application(self, application_name: str) -> ApplicationCloseResult:
        self.calls.append(f"close_application:{application_name}")
        return ApplicationCloseResult(True, "closed", f"{application_name}.exe")

    def mute(self) -> bool:
        self.calls.append("mute")
        return True

    def take_screenshot(self) -> bool:
        self.calls.append("take_screenshot")
        return True

    def scroll(self, amount: int) -> bool:
        self.calls.append(f"scroll:{amount}")
        return True

    def press(self, key: str, presses: int = 1) -> bool:
        self.calls.append(f"press:{key}:{presses}")
        return True

    def hotkey(self, *keys: str) -> bool:
        self.calls.append("hotkey:" + "+".join(keys))
        return True


def test_intent_parser_recognizes_required_commands():
    parser = IntentParserService()
    cases = {
        "Open Chrome": VoiceIntentType.OPEN_CHROME,
        "Close Window": VoiceIntentType.CLOSE_APPLICATION,
        "Copy": VoiceIntentType.COPY,
        "Paste": VoiceIntentType.PASTE,
        "Scroll Up": VoiceIntentType.SCROLL_UP,
        "Scroll Down": VoiceIntentType.SCROLL_DOWN,
        "Volume Up": VoiceIntentType.VOLUME_UP,
        "Volume Down": VoiceIntentType.VOLUME_DOWN,
        "Mute": VoiceIntentType.MUTE,
        "Take Screenshot": VoiceIntentType.TAKE_SCREENSHOT,
    }
    for phrase, expected in cases.items():
        result = parser.parse(phrase)
        assert result.intent == expected, phrase
        assert result.confidence >= 0.85


def test_intent_parser_prioritizes_close_over_open_chrome():
    parser = IntentParserService()
    closed = parser.parse("Close Chrome")
    assert closed.intent == VoiceIntentType.CLOSE_APPLICATION
    assert closed.target == "chrome"

    opened = parser.parse("Open Chrome")
    assert opened.intent == VoiceIntentType.OPEN_CHROME
    assert opened.target == "chrome"

    # Must never fuzzy-match close→open because of shared "chrome".
    assert parser.parse("close chrome").intent != VoiceIntentType.OPEN_CHROME
    assert parser.parse("close chrom").intent == VoiceIntentType.CLOSE_APPLICATION


def test_intent_parser_recognizes_microsoft_edge():
    parser = IntentParserService()
    open_cases = (
        "Open Edge",
        "Open Microsoft Edge",
        "Launch Edge",
    )
    close_cases = (
        "Close Edge",
        "Close Microsoft Edge",
        "Exit Edge",
    )

    for phrase in open_cases:
        result = parser.parse(phrase)
        assert result.intent == VoiceIntentType.OPEN_APPLICATION, phrase
        assert result.target == "edge", phrase
        assert result.confidence >= 0.9, phrase

    for phrase in close_cases:
        result = parser.parse(phrase)
        assert result.intent == VoiceIntentType.CLOSE_APPLICATION, phrase
        assert result.target == "edge", phrase
        assert result.confidence >= 0.9, phrase

    # Chrome / Notepad mappings must remain unchanged.
    assert parser.parse("Open Chrome").intent == VoiceIntentType.OPEN_CHROME
    assert parser.parse("Open Chrome").target == "chrome"
    assert parser.parse("Open Notepad").intent == VoiceIntentType.OPEN_NOTEPAD
    assert parser.parse("Open Notepad").target == "notepad"
    assert parser.parse("Close Chrome").target == "chrome"
    assert parser.parse("Close Notepad").target == "notepad"


def test_intent_parser_unknown_and_empty():
    parser = IntentParserService()
    assert parser.parse("").intent == VoiceIntentType.NO_INTENT
    assert parser.parse("make coffee").intent == VoiceIntentType.NO_INTENT


def test_intent_parser_tolerates_whisper_near_misses():
    parser = IntentParserService()
    assert parser.parse("open chrom").intent == VoiceIntentType.OPEN_CHROME
    assert parser.parse("Okay, open Chrome please").intent == VoiceIntentType.OPEN_CHROME
    assert parser.parse("take a screenshot").intent == VoiceIntentType.TAKE_SCREENSHOT


def test_dispatcher_executes_mute_and_screenshot():
    desktop = _FakeDesktop()
    dispatcher = AutomationDispatcher(desktop)
    parser = IntentParserService()

    mute = dispatcher.dispatch(parser.parse("mute"))
    shot = dispatcher.dispatch(parser.parse("take screenshot"))
    unknown = dispatcher.dispatch(parser.parse("fly away"))
    close_chrome = dispatcher.dispatch(parser.parse("close chrome"))

    assert mute.success is True
    assert mute.message == "Muted"
    assert shot.success is True
    assert shot.message == "Screenshot saved"
    assert unknown.success is False
    assert unknown.message == "Unknown command."
    assert close_chrome.success is True
    assert close_chrome.intent == VoiceIntentType.CLOSE_APPLICATION
    assert close_chrome.message == "Chrome closed"
    assert desktop.calls == ["mute", "take_screenshot", "close_application:chrome"]


def test_voice_pipeline_reuses_action_engine_gate():
    desktop = _FakeDesktop()
    pipeline = VoiceCommandPipeline(
        intent_parser=IntentParserService(),
        action_engine=_FakeActionEngine(cooldown_active=False),
        automation_dispatcher=AutomationDispatcher(desktop),
    )
    intent, message = pipeline.handle_transcript("open chrome")
    assert intent == "OPEN_CHROME"
    assert message == "Chrome opened"
    assert desktop.calls == ["open_chrome"]

    # ActionEngine is consulted even when cooldown is marked; desktop voice
    # commands still execute (eye cooldown timers advance only on eye update).
    cooled = VoiceCommandPipeline(
        intent_parser=IntentParserService(),
        action_engine=_FakeActionEngine(cooldown_active=True),
        automation_dispatcher=AutomationDispatcher(desktop),
    )
    intent, message = cooled.handle_transcript("mute")
    assert intent == "MUTE"
    assert message == "Muted"
    assert desktop.calls[-1] == "mute"


def test_voice_pipeline_empty_and_unknown():
    pipeline = VoiceCommandPipeline(
        intent_parser=IntentParserService(),
        action_engine=_FakeActionEngine(),
        automation_dispatcher=AutomationDispatcher(_FakeDesktop()),
    )
    assert pipeline.handle_transcript("   ") == ("NO_INTENT", "Empty speech.")
    assert pipeline.handle_transcript("dance") == ("NO_INTENT", "Unknown command.")


def test_voice_recognition_mode_and_ptt_state():
    service = VoiceRecognitionService(config=VoiceRecognitionConfig(listen_mode=ListenMode.CONTINUOUS))
    state = service.set_mode("push_to_talk")
    assert state.listenMode == "push_to_talk"

    blocked = service.push_to_talk_start()
    assert blocked.error is not None

    # Simulate listening without opening the microphone thread.
    service._listening = True
    active = service.push_to_talk_start()
    assert active.pushToTalkActive is True
    assert active.executionStatus == "Push-to-talk active"

    released = service.push_to_talk_stop()
    assert released.pushToTalkActive is False
