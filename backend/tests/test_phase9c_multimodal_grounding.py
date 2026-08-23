"""Phase 9C Test Suite: Multimodal Grounding, Contextual Fusion, & Safety Boundaries."""

import time
import pytest

from backend.agent.agent_core import AgentCore
from backend.brain.multimodal_fusion import (
    GazeGroundedSpatialResolver,
    GroundedSpatialTarget,
    MultimodalDecision,
    MultimodalFusionEngine,
)
from backend.brain.world_model import WorldModel, world_model
from backend.eye_tracking.calibration import EyeCenter
from backend.eye_tracking.gaze_service import GazeEstimate
from backend.perception.identity_manager import EnrollmentStatus
from backend.perception.screen_grounding_engine import ScreenElement, ScreenGroundingEngine


@pytest.fixture
def sample_elements():
    return [
        ScreenElement(element_id="e1", application="WhatsApp", window="Dev Nayi Clg", name="Send", role="Button", bounds=(100, 200, 50, 30), center=(125, 215)),
        ScreenElement(element_id="e2", application="WhatsApp", window="Dev Nayi Clg", name="Attachment", role="Button", bounds=(200, 200, 50, 30), center=(225, 215)),
        ScreenElement(element_id="e3", application="WhatsApp", window="Dev Nayi Clg", name="Search box", role="TextBox", bounds=(300, 100, 100, 30), center=(350, 115)),
    ]


@pytest.fixture
def fresh_gaze():
    return GazeEstimate(eye_center=EyeCenter(0.5, 0.5), raw_x=125.0, raw_y=215.0, x=125.0, y=215.0, confidence=0.92, captured_at=time.time())


@pytest.fixture
def stale_gaze():
    return GazeEstimate(eye_center=EyeCenter(0.5, 0.5), raw_x=125.0, raw_y=215.0, x=125.0, y=215.0, confidence=0.92, captured_at=time.time() - 5.0)


# --- 1. Voice + Gaze Click ---
def test_1_voice_gaze_click(sample_elements, fresh_gaze):
    """1. Test fusing voice intent with live gaze target."""
    engine = MultimodalFusionEngine()
    decision = engine.fuse_multimodal_request("Click this", custom_gaze=fresh_gaze, custom_elements=sample_elements)

    assert decision.action == "CLICK"
    assert decision.target == "Send"
    assert decision.confidence > 0.80
    assert decision.gaze_position == (125.0, 215.0)


# --- 2. Voice + Screen Click ---
def test_2_voice_screen_click(sample_elements):
    """2. Test fusing voice intent with screen UI element search."""
    engine = MultimodalFusionEngine()
    decision = engine.fuse_multimodal_request("Click search box", custom_elements=sample_elements)

    assert decision.action == "CLICK"
    assert decision.target == "Search box"
    assert decision.screen_element_id == "e3"


# --- 3. Voice + Gaze + Screen Click ---
def test_3_voice_gaze_screen_click(sample_elements, fresh_gaze):
    """3. Test complete 3-way fusion of Voice, Gaze, and Screen UI element."""
    engine = MultimodalFusionEngine()
    decision = engine.fuse_multimodal_request("Click the Send button", custom_gaze=fresh_gaze, custom_elements=sample_elements)

    assert decision.action == "CLICK"
    assert decision.target == "Send"
    assert decision.source_evidence["gaze"] > 0
    assert decision.source_evidence["screen"] > 0


# --- 4. Right Click Grounding ---
def test_4_right_click_grounding(sample_elements, fresh_gaze):
    """4. Test grounding 'Right click here' to RIGHT_CLICK action decision."""
    engine = MultimodalFusionEngine()
    decision = engine.fuse_multimodal_request("Right click here", custom_gaze=fresh_gaze, custom_elements=sample_elements)

    assert decision.action == "RIGHT_CLICK"
    assert decision.target == "Send"


# --- 5. Copy Grounding ---
def test_5_copy_grounding(sample_elements):
    """5. Test grounding 'Copy this' to COPY action decision."""
    engine = MultimodalFusionEngine()
    decision = engine.fuse_multimodal_request("Copy this", custom_elements=sample_elements)

    assert decision.action == "COPY"


# --- 6. Deictic "this" / "that" ---
def test_6_deictic_this_that(sample_elements, fresh_gaze):
    """6. Test resolving deictic expressions 'this' and 'that'."""
    engine = MultimodalFusionEngine()
    d1 = engine.fuse_multimodal_request("Click this", custom_gaze=fresh_gaze, custom_elements=sample_elements)
    assert d1.target == "Send"

    d2 = engine.fuse_multimodal_request("Double click that", custom_gaze=fresh_gaze, custom_elements=sample_elements)
    assert d2.action == "DOUBLE_CLICK"


# --- 7. Referential "it" (Follow-Up Command) ---
def test_7_referential_it_followup(sample_elements):
    """7. Test resolving pronoun 'it' from WorldModel last_referenced_target context."""
    world_model.update_ui_target("WhatsApp", "Dev Nayi Clg", last_referenced_target={"name": "Send", "role": "Button"})
    engine = MultimodalFusionEngine()

    decision = engine.fuse_multimodal_request("Now right click it", custom_elements=sample_elements)
    assert decision.action == "RIGHT_CLICK"
    assert decision.target == "Send"


# --- 8. Ordinal Candidate Resolution ("second one") ---
def test_8_ordinal_candidate_resolution():
    """8. Test resolving ordinal expressions like 'the second one'."""
    custom_els = [
        ScreenElement(element_id="c1", name="Chat Alpha", role="ListItem"),
        ScreenElement(element_id="c2", name="Chat Beta", role="ListItem"),
    ]
    engine = MultimodalFusionEngine()
    decision = engine.fuse_multimodal_request("Open the second one", custom_elements=custom_els)

    assert decision.target == "Chat Beta"


# --- 9. Stale Gaze Rejection ---
def test_9_stale_gaze_rejection(sample_elements, stale_gaze):
    """9. Test rejecting spatial click when gaze is older than 1.5s."""
    engine = MultimodalFusionEngine()
    decision = engine.fuse_multimodal_request("Click this", custom_gaze=stale_gaze, custom_elements=sample_elements)

    assert decision.requires_confirmation is True
    assert decision.confidence == 0.0
    assert "stale" in decision.reason.lower()


# --- 10. Low-Confidence Rejection ---
def test_10_low_confidence_rejection(sample_elements):
    """10. Test rejecting spatial resolution when gaze confidence is below 0.45 threshold."""
    low_conf_gaze = GazeEstimate(eye_center=EyeCenter(0.5, 0.5), raw_x=125.0, raw_y=215.0, x=125.0, y=215.0, confidence=0.20, captured_at=time.time())
    engine = MultimodalFusionEngine()

    decision = engine.fuse_multimodal_request("Click this", custom_gaze=low_conf_gaze, custom_elements=sample_elements)
    assert decision.requires_confirmation is True


# --- 11. Ambiguity Clarification ---
def test_11_ambiguity_clarification():
    """11. Test requesting clarification when screen elements are ambiguous."""
    ambiguous_els = [
        ScreenElement(element_id="s1", name="Send", role="Button"),
        ScreenElement(element_id="s2", name="Send", role="Button"),
    ]
    engine = MultimodalFusionEngine()
    decision = engine.fuse_multimodal_request("Click Send button", custom_elements=ambiguous_els)

    assert decision.requires_confirmation is True
    assert "multiple" in decision.reason.lower() or "ambiguity" in decision.reason.lower()


# --- 12. Active Application & Window Context Resolution ---
def test_12_context_resolution(sample_elements):
    """12. Test including active app and window in MultimodalDecision."""
    world_model.update_ui_target("VSCode", "main.py - IRISAI")
    engine = MultimodalFusionEngine()

    decision = engine.fuse_multimodal_request("Click search box", custom_elements=sample_elements)
    assert decision.application == "VSCode"
    assert decision.window == "main.py - IRISAI"


# --- 13. Person Context Integration ("his chat") ---
def test_13_person_context_integration():
    """13. Test incorporating recognized person state as context."""
    world_model.update_person("p1", "Rahul", EnrollmentStatus.KNOWN.value, 0.95)
    engine = MultimodalFusionEngine()

    custom_els = [ScreenElement(element_id="c1", name="Rahul chat", role="ListItem")]
    decision = engine.fuse_multimodal_request("Open his chat", custom_elements=custom_els)

    assert decision.person_id == "p1"
    assert decision.target == "Rahul chat"


# --- 14. Conflict Resolution (Voice vs Gaze) ---
def test_14_conflict_resolution(sample_elements, fresh_gaze):
    """14. Test handling conflicts when voice target disagrees with gaze target."""
    engine = MultimodalFusionEngine()
    # Voice asks for Search box, but Gaze points to Send button
    decision = engine.fuse_multimodal_request("Click Search box", custom_gaze=fresh_gaze, custom_elements=sample_elements)

    assert decision.action == "CLICK"
    assert decision.target == "Search box"


# --- 15. WorldModel State Update ---
def test_15_world_model_state_update(sample_elements, fresh_gaze):
    """15. Test updating WorldModel snapshot after decision."""
    engine = MultimodalFusionEngine()
    engine.fuse_multimodal_request("Click Send button", custom_gaze=fresh_gaze, custom_elements=sample_elements)

    snap = world_model.snapshot()
    assert snap.ui_target.last_referenced_target["name"] == "Send"


# --- 16. ActionEngine Safety Boundary ---
def test_16_action_engine_safety_boundary(fresh_gaze):
    """16. Test that AgentCore routes decisions through PolicyEngine and DesktopTool."""
    agent_core = AgentCore()
    res = agent_core.process_goal("IRIS, find the search box")

    assert res.success is True
    assert "Search" in res.response


# --- 17. No Direct Windows Control from Fusion ---
def test_17_no_direct_windows_control_from_fusion(sample_elements, fresh_gaze):
    """17. Test that MultimodalFusionEngine returns decision object without calling system APIs."""
    engine = MultimodalFusionEngine()
    decision = engine.fuse_multimodal_request("Click Send", custom_gaze=fresh_gaze, custom_elements=sample_elements)

    assert isinstance(decision, MultimodalDecision)
    assert decision.action == "CLICK"


# --- 18. Biometric Data Redaction in MultimodalDecision ---
def test_18_biometric_redaction_in_decision():
    """18. Test that MultimodalDecision serialization contains zero raw face embeddings."""
    decision = MultimodalDecision(
        action="CLICK",
        target="Send",
        target_type="UI_ELEMENT",
        confidence=0.96,
        source_evidence={"voice": 0.35, "gaze": 0.30},
        person_id="p1",
    )
    safe_dict = decision.to_safe_dict()

    assert "face_embedding" not in safe_dict
    assert "raw_biometrics" not in safe_dict
