"""Unit tests for Vision Actions & Desktop Interaction Subsystem."""

from __future__ import annotations

from backend.brain.skills.base import SkillExecutionContext
from backend.brain.skills.vision_touch_skill import VisionTouchSkill
from backend.perception.desktop_interaction_planner import DesktopInteractionPlanner
from backend.perception.ocr_service import OCRBoundingBox, OCRResult
from backend.perception.screen_grounding_engine import ScreenGroundingEngine
from backend.perception.ui_action_resolver import UIActionResolver
from backend.perception.visual_action_verifier import VisualActionVerifier
from backend.perception.visual_context import VisualContext


def test_ui_action_resolver_parsing():
    resolver = UIActionResolver()
    ref1 = resolver.resolve_target("Click Save")
    assert ref1.target_phrase == "Save"

    ref2 = resolver.resolve_target("Open the first search result")
    assert ref2.ordinal_index == 0


def test_screen_grounding_engine():
    ocr_res = OCRResult(
        full_text="Save Cancel Submit",
        boxes=[
            OCRBoundingBox(text="Save", x=100, y=200, width=50, height=30, confidence=0.95),
            OCRBoundingBox(text="Cancel", x=200, y=200, width=60, height=30, confidence=0.90),
        ],
    )
    resolver = UIActionResolver()
    target_ref = resolver.resolve_target("Click Save")

    grounding = ScreenGroundingEngine()
    pt = grounding.ground_target(ocr_res, target_ref)

    assert pt is not None
    assert pt.x == 125  # 100 + 25
    assert pt.y == 215  # 200 + 15
    assert pt.text_label == "Save"


def test_desktop_interaction_planner_and_verifier():
    planner = DesktopInteractionPlanner()
    ocr_res = OCRResult(full_text="Save", boxes=[OCRBoundingBox(text="Save", x=100, y=200, width=50, height=30)])
    target_ref = UIActionResolver().resolve_target("Click Save")
    pt = ScreenGroundingEngine().ground_target(ocr_res, target_ref)

    plan = planner.build_click_plan(pt)
    assert plan.steps[0].intent == "CLICK_AT"
    assert plan.steps[0].params["x"] == 125

    verifier = VisualActionVerifier()
    c1 = VisualContext(app_title="Doc 1", visible_text="Text 1")
    c2 = VisualContext(app_title="Doc 2", visible_text="Text 2")
    assert verifier.verify_change(c1, c2) is True


def test_vision_touch_skill():
    skill = VisionTouchSkill()
    assert skill.can_handle("CLICK_VISUAL_TEXT") is True

    res = skill.execute(SkillExecutionContext(intent="CLICK_VISUAL_TEXT", params={"text": "Settings"}))
    assert res.success is True
