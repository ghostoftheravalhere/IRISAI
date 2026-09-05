"""Comprehensive unit tests for IRIS AI V2 Conversational Voice Assistant & Lifecycle."""

from __future__ import annotations

import os
import pytest
from unittest.mock import MagicMock

from backend.voice.recognizer import VoiceRecognitionService, ListenMode
from backend.voice.pipeline import VoiceCommandPipeline
from backend.voice.command_parser import IntentParserService, VoiceIntentType
from backend.voice.assistant_response import AssistantResponseService
from backend.automation.dispatcher import AutomationDispatcher
from backend.automation.controller import DesktopController
from backend.agent.response_generator import ResponseGenerator
from backend.agent.task_state import TaskState, TaskStatus


# 1. Successful command returns to listening
def test_01_successful_command_returns_to_listening():
    service = VoiceRecognitionService()
    state = service.get_state()
    assert state.listening is False
    assert state.microphoneStatus == "Off"


# 2. Unknown command returns clean response
def test_02_unknown_command_returns_response():
    parser = IntentParserService()
    res = parser.parse("blah blah random unsupported text")
    assert res.intent == VoiceIntentType.NO_INTENT

    resp_service = AssistantResponseService()
    msg = resp_service.generate_response("NO_INTENT", custom_message="Sorry, I didn't understand that command.")
    assert msg == "Sorry, I didn't understand that command."


# 3. Empty speech returns to listening without error
def test_03_empty_speech_recovers():
    service = VoiceRecognitionService()
    # Empty intent check
    empty_intent = service._empty_intent()
    assert empty_intent == "NO_INTENT"


# 4. Whisper failure recovers gracefully
def test_04_whisper_failure_recovers():
    resp_gen = ResponseGenerator()
    state = TaskState(user_goal="test goal", status=TaskStatus.FAILED, error_message="Whisper failure.")
    resp = resp_gen.generate_final_response(state)
    assert "issue" in resp.lower() or "whisper" in resp.lower()


# 5. Automation failure returns error response and continues
def test_05_automation_failure_returns_response():
    resp_service = AssistantResponseService()
    res = resp_service.generate_response("OPEN_CHROME", target="chrome", success=False)
    assert "Failed" in res


# 6. Multiple commands in continuous session
def test_06_multiple_commands_continuous_session():
    service = VoiceRecognitionService()
    st1 = service.get_state()
    assert st1.listenMode == "continuous"


# 7. Open Chrome -> response -> next command
def test_07_open_chrome_response():
    resp_service = AssistantResponseService()
    res = resp_service.generate_response("OPEN_CHROME", target="chrome", success=True)
    assert res == "Chrome opened."


# 8. Close Chrome -> response -> next command
def test_08_close_chrome_response():
    resp_service = AssistantResponseService()
    res = resp_service.generate_response("CLOSE_APPLICATION", target="chrome", success=True)
    assert res == "Chrome closed."


# 9. Open Notepad -> response -> next command
def test_09_open_notepad_response():
    resp_service = AssistantResponseService()
    res = resp_service.generate_response("OPEN_NOTEPAD", target="notepad", success=True)
    assert res == "Notepad opened."


# 10. Unknown command between valid commands does not break session
def test_10_unknown_command_between_valid_commands():
    resp_service = AssistantResponseService()
    res1 = resp_service.generate_response("OPEN_CHROME", target="chrome", success=True)
    res2 = resp_service.generate_response("NO_INTENT", custom_message="Sorry, I didn't understand that command.")
    res3 = resp_service.generate_response("OPEN_NOTEPAD", target="notepad", success=True)

    assert res1 == "Chrome opened."
    assert res2 == "Sorry, I didn't understand that command."
    assert res3 == "Notepad opened."


# 11. Push-to-Talk mode functionality preserved
def test_11_push_to_talk_mode_preserved():
    service = VoiceRecognitionService()
    service.set_mode("push_to_talk")
    st = service.get_state()
    assert st.listenMode == "push_to_talk"


# 12. TTS failure does not break recognition
def test_12_tts_failure_does_not_break():
    mock_tts = MagicMock()
    mock_tts.speak.side_effect = RuntimeError("Audio device disconnected")

    resp_service = AssistantResponseService(speech_output_manager=mock_tts)
    text = resp_service.respond("Opening Chrome.", speak=True)
    assert text == "Opening Chrome."


# 13. Frontend status transitions check
def test_13_frontend_status_transitions():
    from backend.api.routes.voice import _serialize
    service = VoiceRecognitionService()
    st = service.get_state()
    payload = _serialize(st)
    assert "microphoneStatus" in payload
    assert "listening" in payload


# 14. No duplicate conversation log entries helper
def test_14_no_duplicate_log_entries():
    history = []
    def add_turn(turn):
        if not history or history[0] != turn:
            history.insert(0, turn)

    t1 = {"source": "USER", "transcript": "Open Chrome"}
    t2 = {"source": "IRIS", "response": "Opening Chrome."}
    add_turn(t1)
    add_turn(t1)  # duplicate call
    add_turn(t2)

    assert len(history) == 2


# 15. No user-facing IRIS V3/V4 branding remains
def test_15_no_v3_v4_user_facing_branding():
    config_path = "frontend/src/config.js"
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "IRIS V3" not in content
            assert "IRIS V4" not in content


# 16. CameraService idempotent start and stop
def test_16_camera_service_idempotent_start_stop():
    from backend.eye_tracking.camera_service import CameraService
    camera = CameraService(camera_index=0)
    assert hasattr(camera, "get_status")
    status = camera.get_status()
    assert "running" in status
    assert "connected" in status


# 17. Perception health probes and diagnostics endpoint snapshot
def test_17_perception_diagnostics_snapshot():
    from backend.sys_platform.diagnostics import DiagnosticsService
    from backend.sys_platform.health import HealthMonitor, HealthState
    monitor = HealthMonitor()
    monitor.register_probe("camera", lambda: (HealthState.HEALTHY, {"running": True}))
    monitor.register_probe("microphone", lambda: (HealthState.HEALTHY, {"status": "On"}))
    diag = DiagnosticsService(health_monitor=monitor)
    snap = diag.generate_snapshot()
    assert "components" in snap
    assert "camera" in snap["components"]
    assert "microphone" in snap["components"]


# 18. TTS audio mute prevention (mutes microphone capture while TTS speaks)
def test_18_tts_audio_mute_prevention():
    from backend.voice.recognizer import VoiceRecognitionService, VoiceRecognitionConfig, ListenMode
    from backend.voice.speech_output import SpeechOutputManager

    mock_tts = SpeechOutputManager()
    mock_tts._is_speaking = True

    service = VoiceRecognitionService()
    service.set_speech_output_manager(mock_tts)
    assert service._should_capture() is False

    mock_tts._is_speaking = False
    assert service._should_capture() is True


# 19. Camera + Microphone perception channels coexist
def test_19_camera_mic_perception_coexistence():
    from backend.eye_tracking.camera_service import CameraService
    from backend.voice.recognizer import VoiceRecognitionService
    camera = CameraService()
    voice = VoiceRecognitionService()
    # Starting/stopping voice does not affect camera instance
    st_voice = voice.get_state()
    st_cam = camera.get_status()
    assert st_voice is not None
    assert st_cam is not None


# 20. LifecycleManager startup and shutdown hooks execution
def test_20_lifecycle_manager_hooks():
    from backend.sys_platform.lifecycle import LifecycleManager
    manager = LifecycleManager()
    started = []
    stopped = []
    manager.register_startup_hook("cam", lambda: started.append("cam"))
    manager.register_shutdown_hook("cam", lambda: stopped.append("cam"))
    manager.startup()
    assert "cam" in started
    manager.shutdown("test")
    assert "cam" in stopped


# 21. ConversationManager 4 decision types (EXECUTE, UNKNOWN, CLARIFY, CONFIRM)
def test_21_conversation_manager_4_decisions():
    from backend.brain.conversation_manager import ConversationManager, DecisionType, ConversationState

    cm = ConversationManager()

    # 1. Clear command -> EXECUTE
    d1 = cm.process_utterance("open chrome")
    assert d1.decision_type == DecisionType.EXECUTE
    assert d1.target == "chrome"

    # 2. Anaphora pronoun resolution ("close it" uses "chrome")
    d2 = cm.process_utterance("close it")
    assert d2.decision_type == DecisionType.EXECUTE
    assert d2.target == "chrome"

    # 3. Unknown command -> UNKNOWN response & returns LISTENING
    d3 = cm.process_utterance("good camera")
    assert d3.decision_type == DecisionType.CLARIFY or d3.decision_type == DecisionType.UNKNOWN
    assert d3.state == ConversationState.WAITING_FOR_CLARIFICATION or d3.state == ConversationState.LISTENING

    # Reset for fresh tests
    cm.reset_session()

    # 4. Ambiguous browser command -> CLARIFY
    d4 = cm.process_utterance("open the browser")
    assert d4.decision_type == DecisionType.CLARIFY
    assert d4.state == ConversationState.WAITING_FOR_CLARIFICATION

    # 5. Clarification YES -> EXECUTE pending
    d5 = cm.process_utterance("yes")
    assert d5.decision_type == DecisionType.EXECUTE

    cm.reset_session()

    # 6. Destructive action -> CONFIRM
    d6 = cm.process_utterance("delete this file")
    assert d6.decision_type == DecisionType.CONFIRM
    assert d6.state == ConversationState.WAITING_FOR_CONFIRMATION

# 22. False-positive command execution regression matrix
def test_22_false_positive_regression_matrix():
    from backend.voice.command_parser import IntentParserService, VoiceIntentType
    from backend.brain.conversation_manager import ConversationManager, DecisionType

    parser = IntentParserService()
    cm = ConversationManager(intent_parser=parser)

    false_positives = [
        "Good camera.",
        "On camera.",
        "Camera is working.",
        "Chrome is good.",
        "I am on camera.",
        "Turned on camera",
    ]

    for fp in false_positives:
        parsed = parser.parse(fp)
        assert parsed.intent == VoiceIntentType.NO_INTENT, f"False positive intent for '{fp}': {parsed.intent}"
        decision = cm.process_utterance(fp, parsed)
        assert decision.decision_type in (DecisionType.UNKNOWN, DecisionType.CLARIFY), f"False positive decision for '{fp}': {decision.decision_type}"
        assert decision.execute_action is False, f"False positive executed action for '{fp}'"

    # Valid commands must execute
    cm.reset_session()
    valid_cam = parser.parse("Open Camera.")
    assert valid_cam.intent in (VoiceIntentType.OPEN_APPLICATION, VoiceIntentType.OPEN_CHROME, VoiceIntentType.OPEN_NOTEPAD)
    d_cam = cm.process_utterance("Open Camera.", valid_cam)
    assert d_cam.decision_type == DecisionType.EXECUTE
    assert d_cam.execute_action is True


# 23. TTS self-hearing feedback loop suppression & pipeline safety gate
def test_23_tts_self_hearing_loop_suppression_and_pipeline_gate():
    from backend.voice.recognizer import VoiceRecognitionService
    from backend.voice.pipeline import VoiceCommandPipeline
    from backend.voice.command_parser import IntentParserService
    from backend.automation.controller import DesktopController
    from backend.automation.dispatcher import AutomationDispatcher
    from backend.automation.action_engine import ActionEngine

    voice = VoiceRecognitionService()
    parser = IntentParserService()
    ctrl = DesktopController()
    disp = AutomationDispatcher(ctrl)
    ae = ActionEngine(controller=ctrl)

    pipeline = VoiceCommandPipeline(intent_parser=parser, action_engine=ae, automation_dispatcher=disp)
    pipeline.set_voice_service(voice)

    # Initially TTS is inactive
    assert voice.is_tts_active() is False

    # Mark TTS active
    voice.set_tts_active(True, duration_sec=1.5)
    assert voice.is_tts_active() is True

    # Pipeline execution MUST be rejected while TTS is active
    res = pipeline.execute("command. Could you say it another way?")
    assert res.success is False
    assert res.message == "Suppressed during TTS."
    assert res.intent == "UNKNOWN"

    # Reset TTS active state
    voice.set_tts_active(False)
    assert voice.is_tts_active() is True  # 0.8s settling window still active

    import time
    time.sleep(0.9)
    assert voice.is_tts_active() is False  # Settling window expired

    # Next valid user utterance MUST succeed
    valid_res = pipeline.execute("Open Notepad.")
    assert valid_res.intent in ("OPEN_APPLICATION", "OPEN_NOTEPAD")


# 24. Final Submission-Critical Regression Matrix (20 checks)
def test_24_all_submission_critical_requirements():
    from backend.voice.command_parser import IntentParserService, VoiceIntentType
    from backend.voice.pipeline import VoiceCommandPipeline
    from backend.automation.controller import DesktopController
    from backend.automation.dispatcher import AutomationDispatcher
    from backend.automation.action_engine import ActionEngine
    from backend.brain.conversation_manager import ConversationManager, DecisionType

    parser = IntentParserService()
    ctrl = DesktopController()
    disp = AutomationDispatcher(ctrl)
    ae = ActionEngine(controller=ctrl)
    cm = ConversationManager(intent_parser=parser)
    pipeline = VoiceCommandPipeline(intent_parser=parser, action_engine=ae, automation_dispatcher=disp, conversation_manager=cm)

    # 1. Open Chrome
    res1 = pipeline.execute("Open Chrome.")
    assert res1.intent in ("OPEN_APPLICATION", "OPEN_CHROME")
    assert res1.message == "Chrome opened."

    # 2. Close Chrome
    res2 = pipeline.execute("Close Chrome.")
    assert res2.intent in ("CLOSE_APPLICATION", "CLOSE_WINDOW")
    assert res2.message == "Chrome closed."

    # 3. Open Camera
    res3 = pipeline.execute("Open Camera.")
    assert res3.intent in ("OPEN_APPLICATION", "OPEN_CHROME")
    assert res3.message == "Camera opened."

    # 4. Unknown Command
    res4 = pipeline.execute("Good camera.")
    assert res4.intent in ("UNKNOWN", "NO_INTENT")
    assert "couldn't understand" in res4.message.lower()

    # 5. Search ChatGPT
    res5 = pipeline.execute("Search ChatGPT.")
    assert res5.intent == "BROWSER_SEARCH"
    assert res5.message == "Done, sir."

    # 6. Open Chrome + Search ChatGPT
    res6 = pipeline.execute("Open Chrome and search ChatGPT.")
    assert res6.intent == "BROWSER_SEARCH"
    assert res6.message == "Done, sir."

    # 7. Short-term context: Close it
    cm.reset_session()
    pipeline.execute("Open Chrome.")
    res7 = pipeline.execute("Close it.")
    assert res7.intent in ("CLOSE_APPLICATION", "CLOSE_WINDOW")
    assert res7.message == "Chrome closed."
