"""Unit tests for TranscriptNormalizer service and data-driven rules."""

from __future__ import annotations

from backend.automation.controller import DesktopController
from backend.automation.dispatcher import AutomationDispatcher
from backend.voice.command_parser import IntentParserService, VoiceIntentType
from backend.voice.normalizer import NormalizationRule, TranscriptNormalizer
from backend.voice.pipeline import VoiceCommandPipeline


class _FakeActionEngine:
    def get_latest_state(self):
        from types import SimpleNamespace
        return SimpleNamespace(
            action=SimpleNamespace(value="NO_ACTION"),
            cooldownActive=False,
            cursorPaused=False,
        )


class _FakeDesktop(DesktopController):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def open_chrome(self) -> bool:
        self.calls.append("open_chrome")
        return True

    def open_notepad(self) -> bool:
        self.calls.append("open_notepad")
        return True

    def close_window(self) -> bool:
        self.calls.append("close_window")
        return True

    def take_screenshot(self) -> bool:
        self.calls.append("take_screenshot")
        return True


def test_rule_open_edge_substitution():
    normalizer = TranscriptNormalizer()
    assert normalizer.normalize("Open it") == "Open edge"
    assert normalizer.normalize("Please open it") == "Please open edge"
    assert normalizer.normalize("Launch it") == "Launch edge"
    assert normalizer.normalize("Start it") == "Start edge"


def test_rule_open_chrome_substitutions():
    normalizer = TranscriptNormalizer()
    assert normalizer.normalize("Open curl") == "Open chrome"
    assert normalizer.normalize("Please open curl") == "Please open chrome"
    assert normalizer.normalize("Open crow") == "Open chrome"
    assert normalizer.normalize("Open chrom") == "Open chrome"


def test_rule_compound_words():
    normalizer = TranscriptNormalizer()
    assert normalizer.normalize("Open note pad") == "Open notepad"
    assert normalizer.normalize("Take a screen shot") == "Take a screenshot"


def test_normalizer_leaves_unmatched_phrases_intact():
    normalizer = TranscriptNormalizer()
    assert normalizer.normalize("Open Chrome") == "Open Chrome"
    assert normalizer.normalize("Copy text") == "Copy text"
    assert normalizer.normalize("Volume up") == "Volume up"
    assert normalizer.normalize("") == ""
    assert normalizer.normalize(None) == ""


def test_normalizer_integrated_with_voice_pipeline():
    desktop = _FakeDesktop()
    pipeline = VoiceCommandPipeline(
        intent_parser=IntentParserService(),
        action_engine=_FakeActionEngine(),
        automation_dispatcher=AutomationDispatcher(desktop),
    )

    # "Open it" normalized to "Open edge" -> parsed as OPEN_APPLICATION edge
    intent, msg = pipeline.handle_transcript("Open it")
    assert intent == VoiceIntentType.OPEN_APPLICATION.value

    # "Please open curl" normalized to "Please open chrome" -> parsed as OPEN_CHROME
    intent_chrome, msg_chrome = pipeline.handle_transcript("Please open curl")
    assert intent_chrome == VoiceIntentType.OPEN_CHROME.value
    assert desktop.calls == ["open_chrome"]
