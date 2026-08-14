"""Natural Language UI Action Resolver Service."""

from __future__ import annotations

import re

from backend.perception.vision_action_models import VisualTargetRef
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_CLICK_PREFIX_REGEX = re.compile(r"^(?:click|press|open|select|tap)\s+", re.IGNORECASE)


from backend.perception.ui_automation_engine import UIAutomationEngine
from backend.perception.ui_automation_models import InteractionMode
from backend.perception.vision_action_models import VisualTargetRef
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_CLICK_PREFIX_REGEX = re.compile(r"^(?:click|press|open|select|tap)\s+", re.IGNORECASE)


class UIActionResolver:
    """Parses natural language visual requests into structured VisualTargetRef models with UIA-first priority."""

    def __init__(self, uia_engine: UIAutomationEngine | None = None) -> None:
        self._uia_engine = uia_engine or UIAutomationEngine()

    def resolve_target(self, text: str) -> VisualTargetRef:
        """Parse phrase like 'Click Save' using UIA accessibility tree first, falling back to OCR."""
        cleaned = _CLICK_PREFIX_REGEX.sub("", text.strip())

        ordinal = 0
        if "first" in cleaned.lower():
            ordinal = 0
            cleaned = re.sub(r"\bfirst\b", "", cleaned, flags=re.IGNORECASE).strip()
        elif "second" in cleaned.lower():
            ordinal = 1
            cleaned = re.sub(r"\bsecond\b", "", cleaned, flags=re.IGNORECASE).strip()

        target_phrase = cleaned or text.strip()

        # Priority 1: UIA Accessibility Lookup
        uia_el = self._uia_engine.find_element(target_phrase)
        if uia_el:
            logger.info("UIActionResolver resolved '%s' via UIA Accessibility (%s)", target_phrase, uia_el.role)
            return VisualTargetRef(
                target_phrase=target_phrase,
                element_type=uia_el.role.lower(),
                ordinal_index=ordinal,
                confidence=0.98,
            )

        # Priority 2: Fallback to OCR visual grounding
        logger.info("UIActionResolver falling back to OCR grounding for '%s'", target_phrase)
        return VisualTargetRef(
            target_phrase=target_phrase,
            element_type="button",
            ordinal_index=ordinal,
            confidence=0.85,
        )
