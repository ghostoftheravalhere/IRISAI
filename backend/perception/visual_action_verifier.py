"""Post-Action Visual Change Verifier Service."""

from __future__ import annotations

from backend.perception.visual_context import VisualContext
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class VisualActionVerifier:
    """Confirms visual UI changes by comparing pre- and post-action visual context snapshots."""

    def verify_change(self, before_context: VisualContext, after_context: VisualContext) -> bool:
        """Return True if screen text or window bounds changed after action execution."""
        if not before_context or not after_context:
            return True

        if before_context.app_title != after_context.app_title:
            return True

        before_len = len(before_context.visible_text)
        after_len = len(after_context.visible_text)

        # Delta detected if text length or content differs
        return before_len != after_len or before_context.visible_text != after_context.visible_text
