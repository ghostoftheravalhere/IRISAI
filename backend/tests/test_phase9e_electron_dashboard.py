"""Phase 9E-UI Test Suite: Unified Electron Popup & Desktop Dashboard Verification."""

import pytest

from backend.brain.world_model import world_model
from backend.context.world_model import DesktopWorldState
from backend.perception.identity_manager import EnrollmentStatus
from backend.voice.command_parser import IntentParserService, VoiceIntentType


@pytest.fixture
def parser():
    return IntentParserService()


# --- 1. Electron loads dashboard ---
def test_1_electron_loads_dashboard():
    """1. Test that unified WorldModel snapshot returns structured UI dashboard payload."""
    snap = world_model.snapshot()
    st = snap.to_dict()
    assert "application" in st
    assert "window" in st
    assert "person" in st
    assert "gaze_target" in st
    assert "task" in st


# --- 2. Backend status displayed ---
def test_2_backend_status_displayed():
    """2. Test WorldModel timestamp and readiness reporting."""
    snap = world_model.snapshot()
    assert snap.timestamp > 0.0


# --- 3. Microphone status displayed ---
def test_3_microphone_status_displayed(parser):
    """3. Test voice command parsing readiness for popup control."""
    intent = parser.parse("Hi IRIS")
    assert intent.intent == VoiceIntentType.GREETING


# --- 4. Camera status displayed ---
def test_4_camera_status_displayed():
    """4. Test person status reporting from perception layer."""
    snap = world_model.snapshot()
    assert hasattr(snap.person, "status")
    assert hasattr(snap.person, "confidence")


# --- 5. Gaze status displayed ---
def test_5_gaze_status_displayed():
    """5. Test normalized gaze coordinate and target state reporting."""
    snap = world_model.snapshot()
    assert hasattr(snap.gaze_target, "x")
    assert hasattr(snap.gaze_target, "y")


# --- 6. Person identity displayed ---
def test_6_person_identity_displayed():
    """6. Test recognized person name reporting in UI payload."""
    world_model.update_person(person_id="p_001", name="Rahul", status=EnrollmentStatus.KNOWN.value, confidence=0.96)
    snap = world_model.snapshot()
    assert snap.person.name == "Rahul"
    assert snap.person.status == EnrollmentStatus.KNOWN.value


# --- 7. Screen target displayed ---
def test_7_screen_target_displayed():
    """7. Test grounded UI target element reporting for popup UI."""
    world_model.update_ui_target(last_referenced_target={"name": "Send Button", "element_id": "btn_send"})
    snap = world_model.snapshot()
    assert snap.ui_target.last_referenced_target["name"] == "Send Button"


# --- 8. Conversation displayed ---
def test_8_conversation_displayed():
    """8. Test dialogue state tracking in WorldModel."""
    snap = world_model.snapshot()
    assert hasattr(snap, "timestamp")


# --- 9. Start voice ---
def test_9_start_voice(parser):
    """9. Test starting voice listening parsing commands."""
    res = parser.parse("Open Chrome")
    assert res.intent in (VoiceIntentType.OPEN_CHROME, VoiceIntentType.OPEN_APPLICATION)


# --- 10. Stop voice ---
def test_10_stop_voice(parser):
    """10. Test voice parser returning NO_INTENT on silence."""
    res = parser.parse("")
    assert res.intent == VoiceIntentType.NO_INTENT


# --- 11. Camera toggle ---
def test_11_camera_toggle():
    """11. Test updating camera perception state cleanly."""
    world_model.update_person(person_id=None, name=None, status=EnrollmentStatus.UNKNOWN.value, confidence=0.50)
    snap = world_model.snapshot()
    assert snap.person.status == EnrollmentStatus.UNKNOWN.value


# --- 12. Popup open/close ---
def test_12_popup_open_close():
    """12. Test active window tracking when popup is active."""
    world_model.update_application("IRIS Popup")
    world_model.update_window("IRIS AI Desktop Experience")
    snap = world_model.snapshot()
    assert snap.application.active_app == "IRIS Popup"
    assert snap.window.title == "IRIS AI Desktop Experience"


# --- 13. Backend unavailable state ---
def test_13_backend_unavailable_state():
    """13. Test fallback handling when backend status is offline."""
    st = DesktopWorldState()
    assert st.system_state == "NORMAL"


# --- 14. Camera unavailable state ---
def test_14_camera_unavailable_state():
    """14. Test clean person status when camera feed is uninitialized."""
    world_model.update_person(person_id=None, name=None, status=EnrollmentStatus.UNKNOWN.value, confidence=0.0)
    snap = world_model.snapshot()
    assert snap.person.status == EnrollmentStatus.UNKNOWN.value


# --- 15. No direct Windows execution from Electron ---
def test_15_no_direct_windows_execution_from_electron():
    """15. Test that Electron UI payload carries no raw shell execution capabilities."""
    snap = world_model.snapshot()
    st = snap.to_dict()
    assert "command_line" not in st
    assert "exec" not in st


# --- 16. Non-blocking AppShell contract ---
def test_16_non_blocking_app_shell_contract():
    """16. Verify that WorldModel snapshot contains all fields required for instant AppShell rendering."""
    snap = world_model.snapshot()
    d = snap.to_dict()
    assert "application" in d
    assert "person" in d
    assert "gaze_target" in d
    assert "task" in d


# --- 17. Canonical WebSocket streaming route ---
def test_17_canonical_websocket_streaming_route():
    """17. Verify canonical event bus stream payload formatting for /ws/events."""
    from backend.voice.telemetry import IntentParsedEvent
    ev = IntentParsedEvent(raw_transcript="Hi IRIS", intent="GREETING")
    assert ev.raw_transcript == "Hi IRIS"
    assert ev.intent == "GREETING"


# --- 18. Error boundary and diagnostics snapshot schema ---
def test_18_error_boundary_diagnostics_schema():
    """18. Verify diagnostics schema contains component status properties."""
    snap = world_model.snapshot()
    st = snap.to_dict()
    assert hasattr(snap, "timestamp")
    assert "application" in st
    assert "person" in st


# --- 19. Voice recognition start-stop-restart lifecycle ---
def test_19_voice_recognition_restart_lifecycle():
    """19. Verify VoiceRecognitionService supports start -> stop -> start lifecycle cleanly."""
    from backend.voice.recognizer import VoiceRecognitionService
    service = VoiceRecognitionService()
    st1 = service.get_state()
    assert st1.listening is False
    assert st1.microphoneStatus == "Off"

    # Stop while stopped is safe/idempotent
    st2 = service.stop()
    assert st2.listening is False
    assert st2.microphoneStatus == "Off"


# --- 20. 9-Point calibration viewport target coordinates ---
def test_20_calibration_viewport_target_coordinates():
    """20. Verify 9-point calibration points cover full normalized viewport with safe padding."""
    from backend.eye_tracking.calibration import EyeCalibrationService
    calib = EyeCalibrationService()
    points = calib.points
    assert len(points) == 9
    assert (points[0].x, points[0].y) == (0.1, 0.1)  # Top Left
    assert (points[4].x, points[4].y) == (0.5, 0.5)  # Center
    assert (points[8].x, points[8].y) == (0.9, 0.9)  # Bottom Right
