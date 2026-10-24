"""Unit tests for Phase 1 & Phase 2 Voice Module ('Look & Say' Multimodal Action Engine)."""

import time
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from backend.voice.command_engine import COMMAND_GRAMMAR, VoskCommandEngine
from backend.voice.action_engine import MultimodalActionDispatcher


class TestVoskCommandEngine:
    """Test suite for VoskCommandEngine command grammar parsing and fallback mode."""

    def test_grammar_vocabulary_list(self):
        expected_commands = [
            "click", "tap",
            "right click",
            "double click",
            "hold", "drag",
            "release", "drop",
            "scroll up", "scroll down",
            "stop"
        ]
        for cmd in expected_commands:
            assert cmd in COMMAND_GRAMMAR

    def test_text_command_parsing(self):
        engine = VoskCommandEngine(model_path=None)
        assert engine.mock_mode is True or engine.ready is False

        for cmd in COMMAND_GRAMMAR:
            assert engine.process_text_command(cmd) == cmd
            assert engine.process_text_command(f"  {cmd.upper()}  ") == cmd

        assert engine.process_text_command("invalid random text") is None
        assert engine.process_text_command("") is None

    def test_process_audio_chunk_mock_fallback(self):
        engine = VoskCommandEngine(model_path=None)
        chunk = np.zeros(1600, dtype=np.float32)
        # Should safely return None in fallback/mock mode without raising exceptions
        assert engine.process_audio_chunk(chunk) is None


class TestMultimodalActionDispatcher:
    """Test suite for MultimodalActionDispatcher mouse actions and continuous scroll daemon."""

    @pytest.fixture
    def dispatcher(self):
        return MultimodalActionDispatcher()

    def test_dispatch_clicks(self, dispatcher):
        with patch("backend.voice.action_engine.win32api") as mock_win32api:
            assert dispatcher.dispatch("click") is True
            assert dispatcher.dispatch("tap") is True
            assert dispatcher.dispatch("right click") is True
            assert dispatcher.dispatch("double click") is True
            assert mock_win32api.mouse_event.called

    def test_dispatch_hold_release(self, dispatcher):
        with patch("backend.voice.action_engine.win32api") as mock_win32api:
            assert dispatcher.dispatch("hold") is True
            assert dispatcher._is_holding is True

            assert dispatcher.dispatch("release") is True
            assert dispatcher._is_holding is False
            assert mock_win32api.mouse_event.called

    def test_scroll_daemon_start_and_stop(self, dispatcher):
        with patch("backend.voice.action_engine.win32api") as mock_win32api:
            # Test scroll up
            assert dispatcher.dispatch("scroll up") is True
            assert dispatcher._scroll_thread is not None
            assert dispatcher._scroll_thread.is_alive()
            assert dispatcher._scroll_delta == 120

            time.sleep(0.12)  # Allow scroll loop to emit at least one wheel event
            assert mock_win32api.mouse_event.called

            # Test stop
            assert dispatcher.dispatch("stop") is True
            assert dispatcher._scroll_thread is None

            # Test scroll down
            assert dispatcher.dispatch("scroll down") is True
            assert dispatcher._scroll_thread is not None
            assert dispatcher._scroll_thread.is_alive()
            assert dispatcher._scroll_delta == -120

            dispatcher.stop_scroll()
            assert dispatcher._scroll_thread is None

    def test_unrecognized_command(self, dispatcher):
        assert dispatcher.dispatch("open browser") is False
        assert dispatcher.dispatch("") is False
