"""Vision Touch Skill Plugin."""

from __future__ import annotations

from typing import Any

from backend.brain.skills.base import (
    SkillDescriptor,
    SkillExecutionContext,
    SkillResult,
)
from backend.perception.ocr_service import OCREngine
from backend.perception.screen_grounding_engine import ScreenGroundingEngine
from backend.perception.ui_action_resolver import UIActionResolver
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class VisionTouchSkill:
    """Skill capability for visual grounding and desktop interaction."""

    def __init__(self) -> None:
        self._resolver = UIActionResolver()
        self._grounding = ScreenGroundingEngine()
        self._ocr = OCREngine()
        self._descriptor = SkillDescriptor(
            skill_id="vision_touch_skill",
            name="Vision Touch Skill",
            version="1.0.0",
            description="Grounds natural language visual phrases onto UI screen coordinates.",
            required_permissions=["vision:read", "desktop:click"],
            capabilities=[
                "CLICK_VISUAL_TEXT",
                "CLICK_VISUAL_COORDINATE",
                "READ_VISUAL_REGION",
            ],
        )

    @property
    def descriptor(self) -> SkillDescriptor:
        return self._descriptor

    def can_handle(self, capability: str) -> bool:
        return capability.upper() in self._descriptor.capabilities

    def execute(self, context: SkillExecutionContext) -> SkillResult:
        intent = context.intent.upper()
        if intent == "CLICK_VISUAL_TEXT":
            phrase = context.params.get("text", context.raw_transcript)
            target_ref = self._resolver.resolve_target(phrase)

            # Synthetic image scan simulation for grounding
            ocr_res = self._ocr.process_image(None)
            pt = self._grounding.ground_target(ocr_res, target_ref)

            if pt:
                return SkillResult(
                    success=True,
                    message=f"Grounded '{target_ref.target_phrase}' to ({pt.x}, {pt.y})",
                    result_data={"x": pt.x, "y": pt.y, "text": pt.text_label},
                )

            return SkillResult(
                success=False,
                message=f"Target phrase '{phrase}' not found on screen.",
            )

        return SkillResult(success=False, message=f"Unsupported intent: {context.intent}")
