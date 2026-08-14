"""Unit tests for Wake Word & Natural Voice Subsystem."""

from __future__ import annotations

from backend.core.events.bus import EventBus
from backend.voice.speech_output import SpeechOutputManager
from backend.voice.voice_session_controller import VoiceSessionController, VoiceSessionState
from backend.voice.wakeword_engine import WakeWordEngine
from backend.voice.wakeword_events import SpeechInterruptedEvent, WakeWordDetectedEvent
from backend.voice.wakeword_manager import WakeWordManager
from backend.voice.wakeword_provider import MockWakeWordProvider


def test_wakeword_engine_detection():
    event_bus = EventBus()
    events_received = []

    def _on_event(e):
        events_received.append(e)

    event_bus.subscribe(WakeWordDetectedEvent, _on_event)

    provider = MockWakeWordProvider()
    engine = WakeWordEngine(provider=provider, event_bus=event_bus)

    # Frame without trigger flag
    det1, kw1, conf1 = engine.process_frame({"pcm": [0.1, 0.2]})
    assert det1 is False

    # Frame with trigger flag
    det2, kw2, conf2 = engine.process_frame({"trigger_wake_word": True})
    assert det2 is True
    assert kw2 == "Hey IRIS"
    assert len(events_received) == 1


def test_wakeword_manager_settings():
    manager = WakeWordManager()
    res = manager.update_settings(sensitivity=0.8, timeout_sec=10.0)

    assert res["sensitivity"] == 0.8
    assert res["auto_timeout_sec"] == 10.0


def test_voice_session_controller_transitions():
    ctrl = VoiceSessionController()
    assert ctrl.state == VoiceSessionState.SLEEPING

    ctrl.set_state(VoiceSessionState.WAKE_DETECTED)
    assert ctrl.state == VoiceSessionState.WAKE_DETECTED

    ctrl.set_state(VoiceSessionState.SPEAKING)
    assert ctrl.state == VoiceSessionState.SPEAKING


def test_speech_output_manager_interruption():
    event_bus = EventBus()
    events_received = []

    def _on_event(e):
        events_received.append(e)

    event_bus.subscribe(SpeechInterruptedEvent, _on_event)

    speech_mgr = SpeechOutputManager(event_bus=event_bus)
    speech_mgr._is_speaking = True

    stopped = speech_mgr.stop(reason="user_stop")
    assert stopped is True
    assert speech_mgr.is_speaking is False
    assert len(events_received) == 1
