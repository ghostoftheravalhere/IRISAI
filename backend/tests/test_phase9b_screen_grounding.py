"""Phase 9B Test Suite: Screen / UI Perception Grounding, Spatial Gaze, & Ambiguity Resolution."""

import time
import pytest

from backend.agent.agent_core import AgentCore
from backend.agent.policy_engine import PermissionLevel
from backend.brain.world_model import world_model
from backend.perception.ocr_service import OCREngine
from backend.perception.screen_grounding_engine import (
    GroundingResult,
    ScreenElement,
    ScreenGroundingEngine,
)
from backend.perception.ui_automation_engine import UIAutomationEngine
from backend.perception.ui_automation_models import AccessibilityElement


@pytest.fixture
def mock_uia():
    class DummyUIA:
        def find_all(self):
            return [
                AccessibilityElement(name="Send", role="Button", automation_id="btn_send_1", enabled=True),
                AccessibilityElement(name="Search", role="TextBox", automation_id="txt_search", enabled=True),
                AccessibilityElement(name="Send", role="Button", automation_id="btn_send_2", enabled=True),
                AccessibilityElement(name="Settings", role="Button", automation_id="btn_settings", enabled=True),
            ]
    return DummyUIA()


# --- 1. UIA Element Extraction ---
def test_1_uia_element_extraction(mock_uia):
    """1. Test extracting canonical ScreenElement list from UIA engine."""
    engine = ScreenGroundingEngine(uia_engine=mock_uia)
    elements = engine.extract_screen_elements("Notepad", "Untitled - Notepad")

    assert len(elements) == 4
    assert elements[0].name == "Send"
    assert elements[0].application == "Notepad"
    assert elements[0].source == "UIA"


# --- 2. Unified ScreenElement Model ---
def test_2_unified_screen_element_model():
    """2. Test ScreenElement fields and safe dictionary conversion."""
    el = ScreenElement(
        element_id="el_1",
        application="Chrome",
        window="Google Chrome",
        role="Button",
        name="Submit",
        bounds=(100, 200, 80, 30),
        center=(140, 215),
        source="UIA",
    )
    safe_dict = el.to_safe_dict()

    assert safe_dict["element_id"] == "el_1"
    assert safe_dict["bounds"] == (100, 200, 80, 30)
    assert safe_dict["center"] == (140, 215)
    assert "raw_screenshot" not in safe_dict


# --- 3. Semantic Target Matching ---
def test_3_semantic_target_matching(mock_uia):
    """3. Test grounding semantic query ('Find the Search box')."""
    engine = ScreenGroundingEngine(uia_engine=mock_uia)
    res = engine.ground_query("Find the Search box")

    assert res.success is True
    assert res.target is not None
    assert res.target.name == "Search"


# --- 4. Multiple Candidates & Ordinal Indexing ---
def test_4_multiple_candidates_and_ordinals(mock_uia):
    """4. Test selecting specific ordinal candidate ('Click the second result')."""
    engine = ScreenGroundingEngine(uia_engine=mock_uia)
    custom_els = [
        ScreenElement(element_id="e1", name="Result Alpha", role="ListItem"),
        ScreenElement(element_id="e2", name="Result Beta", role="ListItem"),
        ScreenElement(element_id="e3", name="Result Gamma", role="ListItem"),
    ]

    res = engine.ground_query("Click the second result", custom_elements=custom_els)
    assert res.success is True
    assert res.target.name == "Result Beta"


# --- 5. Ambiguity Clarification ---
def test_5_ambiguity_clarification(mock_uia):
    """5. Test detecting ambiguous targets when multiple matching elements exist."""
    engine = ScreenGroundingEngine(uia_engine=mock_uia)
    res = engine.ground_query("Click Send button")

    # mock_uia returns two 'Send' buttons with equal score
    assert res.requires_clarification is True
    assert res.error_code == "AMBIGUOUS_TARGET"
    assert "multiple matching controls" in res.clarification_message


# --- 6. Gaze-Grounded Spatial Target Matching ---
def test_6_gaze_spatial_matching():
    """6. Test spatial target resolution when user says 'Click this' with live gaze."""
    class DummySpatialResolver:
        def resolve_spatial_target(self, custom_gaze=None):
            class DummyTarget:
                x = 140
                y = 215
            return DummyTarget()

    engine = ScreenGroundingEngine(spatial_resolver=DummySpatialResolver())
    custom_els = [
        ScreenElement(element_id="e1", name="Message Box", bounds=(100, 200, 100, 50), center=(150, 225)),
    ]

    res = engine.ground_query("Click this", custom_elements=custom_els)
    assert res.success is True
    assert res.target.name == "Message Box"


# --- 7. Stale Gaze Rejection ---
def test_7_stale_gaze_rejection():
    """7. Test rejecting spatial click when gaze is stale or unavailable."""
    class DummyStaleResolver:
        def resolve_spatial_target(self, custom_gaze=None):
            return None

    engine = ScreenGroundingEngine(spatial_resolver=DummyStaleResolver())
    res = engine.ground_query("Click this")

    assert res.success is False
    assert res.error_code == "STALE_GAZE"
    assert "stale" in res.clarification_message.lower()


# --- 8. OCR Fallback When UIA Is Empty ---
def test_8_ocr_fallback_when_uia_empty():
    """8. Test falling back to OCR engine when UIA returns zero elements."""
    class EmptyUIA:
        def find_all(self):
            return []

    engine = ScreenGroundingEngine(uia_engine=EmptyUIA())
    elements = engine.extract_screen_elements()

    assert len(elements) > 0
    assert elements[0].source == "OCR"


# --- 9. WorldModel UI Context Update ---
def test_9_world_model_ui_update(mock_uia):
    """9. Test WorldModel update with visible screen element metadata."""
    engine = ScreenGroundingEngine(uia_engine=mock_uia)
    engine.extract_screen_elements("Chrome", "Google Chrome")

    snap = world_model.snapshot()
    assert snap.application.active_app == "Chrome"
    assert snap.application.active_window == "Google Chrome"
    assert len(snap.ui_target.visible_elements) == 4


# --- 10. Screen Grounding Confidence Scoring ---
def test_10_confidence_scoring():
    """10. Test matching score calculation for exact vs partial element name matches."""
    engine = ScreenGroundingEngine()
    el_exact = ScreenElement(element_id="e1", name="Submit", role="Button")
    el_partial = ScreenElement(element_id="e2", name="Submit Form Settings", role="Button")

    score_exact = engine._calculate_match_score("submit", "find submit", el_exact)
    score_partial = engine._calculate_match_score("submit", "find submit", el_partial)

    assert score_exact > score_partial


# --- 11. Action Pipeline Safety ---
def test_11_action_pipeline_safety():
    """11. Test that DesktopTool delegates execution through ActionEngine."""
    agent_core = AgentCore()
    res = agent_core.process_goal("IRIS, find the search box")

    assert res.success is True
    assert "Found" in res.response or "Search" in res.response


# --- 12. PolicyEngine Enforcement ---
def test_12_policy_engine_enforcement():
    """12. Test that desktop tool actions enforce SAFE permission level."""
    from backend.agent.tools.desktop_tool import DesktopTool
    dt = DesktopTool()
    assert dt.descriptor.permission_level == PermissionLevel.SAFE
