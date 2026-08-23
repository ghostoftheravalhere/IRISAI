"""Voice recognition and intent parsing unit tests."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

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


def test_voice_recognition_silence_does_not_produce_actionable_transcript():
    service = VoiceRecognitionService()
    fake_model = _PromptSensitiveWhisperModel()
    service._model = fake_model

    transcript = service._transcribe(np.zeros(service._config.sample_rate, dtype=np.float32))

    assert transcript == ""
    assert fake_model.calls[-1]["initial_prompt"] is None
    assert fake_model.calls[-1]["vad_filter"] is False
    assert fake_model.calls[-1]["no_speech_threshold"] == service._config.no_speech_threshold


def test_voice_recognition_low_noise_does_not_produce_actionable_transcript():
    service = VoiceRecognitionService()
    fake_model = _PromptSensitiveWhisperModel()
    service._model = fake_model
    rng = np.random.default_rng(7)
    low_noise = rng.normal(0, 0.002, service._config.sample_rate).astype(np.float32)

    transcript = service._transcribe(low_noise)

    assert transcript == ""
    assert fake_model.calls[-1]["initial_prompt"] is None
    assert fake_model.calls[-1]["vad_filter"] is False
    assert fake_model.calls[-1]["no_speech_threshold"] == service._config.no_speech_threshold


def test_voice_recognition_preserves_previous_transcript_on_empty_speech():
    pipeline = VoiceCommandPipeline(
        intent_parser=IntentParserService(),
        action_engine=_FakeActionEngine(),
        automation_dispatcher=AutomationDispatcher(_FakeDesktop()),
    )
    service = VoiceRecognitionService(on_transcript=pipeline.handle_transcript)
    service._model = _PromptSensitiveWhisperModel()

    # Manually simulate a successful transcription callback
    service._latest_transcript = "Open Chrome"
    service._detected_intent = "OPEN_CHROME"
    service._execution_status = "Chrome opened"

    # Now pass empty audio that produces empty transcript
    empty_audio = np.zeros(service._config.sample_rate, dtype=np.float32)
    service._handle_audio(empty_audio)

    state = service.get_state()
    # The previous transcript, intent, and status must be preserved!
    assert state.latestTranscript == "Open Chrome"
    assert state.detectedIntent == "OPEN_CHROME"
    assert state.executionStatus == "Chrome opened"


def test_ptt_bypasses_rms_gating_and_flushes_on_release():
    handled_buffers = []

    class TracedVoiceService(VoiceRecognitionService):
        def _handle_audio(self, audio):
            handled_buffers.append(audio)
            super()._handle_audio(audio)

    service = TracedVoiceService(
        config=VoiceRecognitionConfig(model_size="base", device="cpu", listen_mode=ListenMode.PUSH_TO_TALK)
    )
    service._model = _PromptSensitiveWhisperModel()

    # 1. Verify continuous mode setting remains distinct
    cont_service = VoiceRecognitionService(
        config=VoiceRecognitionConfig(model_size="base", device="cpu", listen_mode=ListenMode.CONTINUOUS)
    )
    assert cont_service._listen_mode == ListenMode.CONTINUOUS

    # 2. Push-To-Talk: activate PTT
    service._listening = True
    service.push_to_talk_start()
    assert service._should_capture() is True

    # Low RMS blocks (0.003 RMS < 0.010 threshold)
    low_rms_block = np.full(4000, 0.003, dtype=np.float32)

    # 3. Simulate PTT loop: accumulates all blocks without RMS gating
    speech_blocks = [low_rms_block.copy(), low_rms_block.copy()]

    # 4. Stop PTT: _should_capture becomes False
    service.push_to_talk_stop()
    assert service._should_capture() is False

    # 5. Flush accumulated PTT buffer to _handle_audio
    if not service._should_capture() and speech_blocks:
        audio = np.concatenate(speech_blocks)
        service._handle_audio(audio)

    # Assert _handle_audio was invoked with full buffer despite low RMS
    assert len(handled_buffers) == 1
    assert len(handled_buffers[0]) == 8000


class _PromptSensitiveWhisperModel:
    """Regression fake: command prompts turn non-speech into command text."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def transcribe(self, audio, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("initial_prompt"):
            return [SimpleNamespace(text="Copy.", no_speech_prob=0.0)], object()
        return [], object()


