"""Central Dialogue Manager Coordinator Subsystem (DEPRECATED).

DEPRECATED: Preferred authoritative DialogueManager is in backend.brain.dialogue_manager.
This module is maintained solely for backward compatibility with legacy dialogue routes and unit tests.
"""

from __future__ import annotations

from threading import RLock
from typing import Any

from backend.brain.orchestrator import BrainOrchestrator, OrchestrationRequest, OrchestrationResponse
from backend.core.events.bus import EventBus
from backend.dialogue.clarification_manager import ClarificationManager
from backend.dialogue.conversation_policy import ConversationPolicy
from backend.dialogue.conversation_session import ConversationSession
from backend.dialogue.dialogue_models import DialoguePolicyAction, DialogueState, DialogueTurn
from backend.dialogue.reference_resolver import ReferenceResolver
from backend.utils.logger import get_logger
from backend.voice.command_parser import IntentParserService, VoiceIntent

logger = get_logger(__name__)


from backend.brain.risk_assessment import RiskLevel, RiskReport


class DialogueManager:
    """Central Dialogue Manager coordinating multi-turn interaction, reference resolution, and policy evaluation."""

    def __init__(
        self,
        orchestrator: BrainOrchestrator | None = None,
        event_bus: EventBus | None = None,
        intent_parser: IntentParserService | None = None,
        enabled: bool = True,
    ) -> None:
        self._orchestrator = orchestrator
        self._event_bus = event_bus
        self._intent_parser = intent_parser or IntentParserService()
        self._session = ConversationSession()
        self._resolver = ReferenceResolver()
        self._clarification_mgr = ClarificationManager()
        self._policy = ConversationPolicy()
        self._enabled = enabled
        self._lock = RLock()

    @property
    def session(self) -> ConversationSession:
        return self._session

    def check_confirmation_required(self, risk_report: RiskReport) -> tuple[bool, str]:
        """Return True and confirmation prompt message if workflow requires explicit confirmation."""
        if risk_report.confirmation_required or risk_report.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            count = len(risk_report.destructive_actions)
            msg = f"Warning: This action has {risk_report.risk_level.value} risk with {count} side-effect(s). Proceed? (YES/NO)"
            logger.info("DialogueManager generated risk confirmation prompt: '%s'", msg)
            return True, msg
        return False, ""

    def process_utterance(self, text: str, source: str = "voice") -> dict[str, Any]:
        """Process a multi-turn utterance with reference resolution and policy routing."""
        with self._lock:
            if not text or not text.strip():
                return {"success": False, "message": "Empty utterance."}

            parsed_intent = self._intent_parser.parse(text)

            # Resolve references (pronouns "it", "that", location "there") using focus stack
            resolved_text, target, query = self._resolver.resolve(
                raw_text=text,
                session=self._session,
                current_target=parsed_intent.target,
                current_query=parsed_intent.query,
            )

            updated_intent = VoiceIntent(
                intent=parsed_intent.intent,
                text=resolved_text,
                target=target,
                query=query,
                confidence=parsed_intent.confidence,
            )

            policy_action = self._policy.evaluate(updated_intent.confidence, updated_intent.intent.value)

            # Record turn in session
            user_turn = DialogueTurn(
                speaker="user",
                raw_text=text,
                parsed_intent=updated_intent.intent.value,
                resolved_target=target,
                resolved_query=query,
                confidence=updated_intent.confidence,
            )
            self._session.add_turn(user_turn)

            if policy_action == DialoguePolicyAction.CLARIFY:
                options = self._clarification_mgr.generate_options(resolved_text)
                self._session.set_state(DialogueState.AWAITING_CLARIFICATION)
                return {
                    "action": "CLARIFY",
                    "resolved_text": resolved_text,
                    "intent": updated_intent.intent.value,
                    "clarification_options": [o.__dict__ for o in options],
                }

            if self._orchestrator is not None:
                req = OrchestrationRequest(source=source, intent=updated_intent, raw_transcript=resolved_text)
                orch_resp = self._orchestrator.process_intent(req)
                return {
                    "action": "EXECUTED",
                    "resolved_text": resolved_text,
                    "intent": orch_resp.intent,
                    "success": orch_resp.success,
                    "message": orch_resp.message,
                }

            return {
                "action": "RESOLVED",
                "resolved_text": resolved_text,
                "intent": updated_intent.intent.value,
                "target": target,
                "query": query,
            }
