"""Conversation Policy Engine."""

from __future__ import annotations

from backend.dialogue.dialogue_models import DialoguePolicyAction
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ConversationPolicy:
    """Determines policy action (DIRECT_EXECUTION, CLARIFY, CONFIRM) for dialogue turns."""

    def evaluate(self, confidence: float, intent_name: str) -> DialoguePolicyAction:
        """Evaluate policy action based on confidence threshold and intent risk."""
        if intent_name in ("SHUTDOWN_SYSTEM", "DELETE_FILE", "WIPE_MEMORY"):
            return DialoguePolicyAction.CONFIRM

        if confidence < 0.70:
            return DialoguePolicyAction.CLARIFY

        return DialoguePolicyAction.DIRECT_EXECUTION
