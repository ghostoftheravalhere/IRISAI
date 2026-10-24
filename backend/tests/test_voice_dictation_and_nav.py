"""Unit tests for Phase 3 (Gaze Dictation / Look & Type) and Phase 4 (Native OS Navigation Commands)."""

import time
from unittest.mock import MagicMock, patch
import pytest

from backend.voice.command_engine import COMMAND_GRAMMAR, VoskCommandEngine
from backend.voice.action_engine import MultimodalActionDispatcher
from backend.voice.keyboard_injector import send_hotkey, type_unicode_text
from backend.voice.dictation_engine import WhisperDictationEngine
from backend.voice.system_navigator import SystemNavigator


class TestKeyboardInjector:
    """Test suite for native Unicode keyboard injector and hotkey sender."""

    def test_type_unicode_text(self):
        assert type_unicode_text("Hello, World! 123") is True
        assert type_unicode_text("") is False

    def test_send_hotkey(self):
        assert send_hotkey(0x12, 0x09) is True  # Alt + Tab
        assert send_hotkey() is False


class TestWhisperDictationEngine:
    """Test suite for WhisperDictationEngine fallback mode."""

    def test_dictation_engine_fallback(self):
        engine = WhisperDictationEngine(model_size="tiny.en")
        assert engine.transcribe_audio_buffer(b"") == ""
        assert engine.transcribe_audio_buffer(b"\x00" * 3200) == ""


class TestSystemNavigator:
    """Test suite for SystemNavigator window control dispatching."""

    @pytest.fixture
    def navigator(self):
        return SystemNavigator()

    def test_dispatch_navigation_actions(self, navigator):
        with patch("backend.voice.system_navigator.win32gui") as mock_win32gui, \
             patch("backend.voice.system_navigator.send_hotkey", return_value=True) as mock_hotkey:
            mock_win32gui.GetForegroundWindow.return_value = 12345
            mock_win32gui.IsZoomed.return_value = False

            assert navigator.dispatch("minimize") is True
            assert navigator.dispatch("maximize") is True
            assert navigator.dispatch("close window") is True
            assert navigator.dispatch("switch app") is True
            assert navigator.dispatch("show desktop") is True
            assert navigator.dispatch("new tab") is True
            assert navigator.dispatch("close tab") is True

    def test_unrecognized_navigation_action(self, navigator):
        assert navigator.dispatch("fly to moon") is False
        assert navigator.dispatch("") is False


class TestPhase3And4MultimodalActionDispatcher:
    """Test suite for MultimodalActionDispatcher handling dictation and OS nav commands."""

    @pytest.fixture
    def dispatcher(self):
        return MultimodalActionDispatcher()

    def test_dictation_mode_toggles(self, dispatcher):
        assert dispatcher.dictation_active is False

        assert dispatcher.dispatch("start dictation") is True
        assert dispatcher.dictation_active is True

        assert dispatcher.dispatch("stop dictation") is True
        assert dispatcher.dictation_active is False

    def test_type_command(self, dispatcher):
        with patch.object(dispatcher, "_left_click") as mock_click:
            assert dispatcher.dispatch("type") is True
            assert mock_click.called
            assert dispatcher._single_type_pending is True

    def test_navigation_command_routing(self, dispatcher):
        with patch.object(dispatcher._navigator, "dispatch", return_value=True) as mock_nav:
            assert dispatcher.dispatch("minimize") is True
            mock_nav.assert_called_with("minimize")

            assert dispatcher.dispatch("switch app") is True
            mock_nav.assert_called_with("switch app")

    def test_expanded_grammar_coverage(self):
        phase3_4_commands = [
            "type", "start dictation", "stop dictation",
            "minimize", "maximize", "close window",
            "switch app", "show desktop",
            "new tab", "close tab"
        ]
        for cmd in phase3_4_commands:
            assert cmd in COMMAND_GRAMMAR
