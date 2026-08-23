"""ConversationManager: Conversational decision layer between Intent Parser and Action Engine.

Evaluates intent & text, manages conversation context, affirmative/negative confirmation,
pronoun resolution ("close it"), and candidate clarification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
import time
from typing import Any

from backend.utils.logger import get_logger
from backend.voice.command_parser import IntentParserService, VoiceIntent, VoiceIntentType

logger = get_logger(__name__)


class DecisionType(str, Enum):
    """Four core decision types produced by ConversationManager."""

    EXECUTE = "EXECUTE"
    CLARIFY = "CLARIFY"
    CONFIRM = "CONFIRM"
    UNKNOWN = "UNKNOWN"


class ConversationState(str, Enum):
    """Conversation session states."""

    IDLE = "IDLE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    EXECUTING = "EXECUTING"
    RESPONDING = "RESPONDING"
    WAITING_FOR_CLARIFICATION = "WAITING_FOR_CLARIFICATION"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"


@dataclass
class ConversationDecision:
    """Outcome produced by ConversationManager decision evaluation."""

    decision_type: DecisionType
    state: ConversationState
    message: str
    intent: VoiceIntentType = VoiceIntentType.NO_INTENT
    target: str | None = None
    query: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    candidates: list[str] = field(default_factory=list)
    execute_action: bool = False
    cancelled: bool = False


class ConversationManager:
    """Manages short-term conversation context, confirmation, clarification, and pronoun resolution."""

    def __init__(
        self,
        intent_parser: IntentParserService | None = None,
        timeout_seconds: float = 30.0,
        voice_service: Any | None = None,
    ) -> None:
        self._intent_parser = intent_parser or IntentParserService()
        self._timeout_seconds = timeout_seconds
        self._voice_service = voice_service

        self._state = ConversationState.IDLE
        self._pending_intent: VoiceIntentType | None = None
        self._pending_target: str | None = None
        self._pending_query: str | None = None
        self._pending_params: dict[str, Any] = {}
        self._pending_question: str | None = None
        self._pending_candidates: list[str] = []
        self._pending_reason: str | None = None

        self._last_command: str | None = None
        self._last_intent: VoiceIntentType | None = None
        self._last_target: str | None = None
        self._last_action: str | None = None
        self._last_response: str | None = None
        self._last_turn_time: float = time.time()
        self._lock = RLock()

    def set_voice_service(self, voice_service: Any) -> None:
        """Attach VoiceRecognitionService for active TTS state queries."""
        with self._lock:
            self._voice_service = voice_service

    def is_tts_active(self) -> bool:
        """Return whether VoiceRecognitionService or SpeechOutputManager is in active TTS output."""
        with self._lock:
            if self._voice_service is not None and hasattr(self._voice_service, "is_tts_active"):
                return self._voice_service.is_tts_active()
            return False

    @property
    def state(self) -> ConversationState:
        with self._lock:
            self._check_timeout_internal()
            return self._state

    @property
    def last_target(self) -> str | None:
        with self._lock:
            return self._last_target

    def reset_session(self) -> None:
        """Reset conversation session state."""
        with self._lock:
            self._state = ConversationState.IDLE
            self._clear_pending_internal()
            self._last_command = None
            self._last_intent = None
            self._last_target = None
            self._last_action = None
            self._last_response = None
            self._last_turn_time = time.time()

    def process_utterance(self, text: str, parsed_intent: VoiceIntent | None = None) -> ConversationDecision:
        """Evaluate an utterance through conversation context, affirmation checks, and decision rules."""
        with self._lock:
            self._check_timeout_internal()
            clean_text = (text or "").strip().lower()
            if not clean_text:
                return ConversationDecision(
                    decision_type=DecisionType.UNKNOWN,
                    state=ConversationState.LISTENING,
                    message="Silence.",
                )

            # 1. Handle pending confirmation/clarification dialogue turns first!
            if self._state == ConversationState.WAITING_FOR_CONFIRMATION:
                return self._handle_confirmation_turn(clean_text)

            if self._state == ConversationState.WAITING_FOR_CLARIFICATION:
                return self._handle_clarification_turn(clean_text)

            # Parse intent if not provided
            intent_obj = parsed_intent or self._intent_parser.parse(clean_text)
            intent_type = intent_obj.intent
            target = intent_obj.target
            query = intent_obj.query
            params = dict(intent_obj.params or {})

            # 2. Pronoun & Anaphora Resolution ("close it", "open it", "close this")
            if target and target.lower() in ("it", "this", "that", "the app", "the window"):
                if self._last_target:
                    logger.info("Anaphora resolved: '%s' -> '%s'", target, self._last_target)
                    target = self._last_target
                elif "close" in clean_text:
                    intent_type = VoiceIntentType.CLOSE_WINDOW
                    target = "window"

            if intent_type == VoiceIntentType.CLOSE_WINDOW and not target and self._last_target:
                target = self._last_target

            # 3. Decision Rules for Specific Intents

            # A. Destructive / Risky Actions -> CONFIRM Decision
            if self._is_destructive_action(clean_text, intent_type, target):
                self._state = ConversationState.WAITING_FOR_CONFIRMATION
                self._pending_intent = intent_type
                self._pending_target = target
                self._pending_query = query
                self._pending_params = params
                self._pending_question = f"Sir, you asked me to {clean_text}. Do you want me to proceed? Please say yes or no."
                self._last_turn_time = time.time()
                return ConversationDecision(
                    decision_type=DecisionType.CONFIRM,
                    state=ConversationState.WAITING_FOR_CONFIRMATION,
                    message=self._pending_question,
                    intent=intent_type,
                    target=target,
                    execute_action=False,
                )

            # B. Ambiguous Application / Camera Targets -> CLARIFY Decision
            if intent_type == VoiceIntentType.NO_INTENT and "camera" in clean_text and clean_text not in ("open camera", "launch camera", "start camera", "close camera", "stop camera"):
                if any(w in clean_text for w in ("good", "nice", "check", "see", "show")):
                    self._state = ConversationState.WAITING_FOR_CLARIFICATION
                    self._pending_intent = VoiceIntentType.OPEN_APPLICATION
                    self._pending_target = "camera"
                    self._pending_question = "Sir, did you mean open the Camera application? Please say yes or no."
                    self._pending_candidates = ["Camera application"]
                    self._last_turn_time = time.time()
                    return ConversationDecision(
                        decision_type=DecisionType.CLARIFY,
                        state=ConversationState.WAITING_FOR_CLARIFICATION,
                        message=self._pending_question,
                        intent=VoiceIntentType.OPEN_APPLICATION,
                        target="camera",
                        candidates=self._pending_candidates,
                        execute_action=False,
                    )

            if (intent_type in (VoiceIntentType.OPEN_APPLICATION, VoiceIntentType.OPEN_CHROME)) and (target == "browser" or "browser" in clean_text):
                self._state = ConversationState.WAITING_FOR_CLARIFICATION
                self._pending_intent = VoiceIntentType.OPEN_APPLICATION
                self._pending_target = "chrome"
                self._pending_question = "Sir, which browser would you like me to open, Chrome or Edge?"
                self._pending_candidates = ["chrome", "edge"]
                self._last_turn_time = time.time()
                return ConversationDecision(
                    decision_type=DecisionType.CLARIFY,
                    state=ConversationState.WAITING_FOR_CLARIFICATION,
                    message=self._pending_question,
                    intent=VoiceIntentType.OPEN_APPLICATION,
                    candidates=self._pending_candidates,
                    execute_action=False,
                )

            # C. Unrecognized / Gibberish Commands -> UNKNOWN Decision
            if intent_type == VoiceIntentType.NO_INTENT:
                logger.info("Unrecognized goal '%s' -> UNKNOWN decision.", clean_text)
                self._state = ConversationState.IDLE
                return ConversationDecision(
                    decision_type=DecisionType.UNKNOWN,
                    state=ConversationState.LISTENING,
                    message="Sir, I couldn't understand that command. Could you say it another way?",
                    intent=VoiceIntentType.NO_INTENT,
                    execute_action=False,
                )

            # D. Clear & Safe Intent -> EXECUTE Decision
            self._state = ConversationState.EXECUTING
            self._last_command = clean_text
            self._last_intent = intent_type
            if target and target.lower() not in ("window", "app"):
                self._last_target = target.lower()
            self._last_turn_time = time.time()

            return ConversationDecision(
                decision_type=DecisionType.EXECUTE,
                state=ConversationState.EXECUTING,
                message=f"Executing {intent_type.value}...",
                intent=intent_type,
                target=target,
                query=query,
                params=params,
                execute_action=True,
            )

    def _handle_confirmation_turn(self, clean_text: str) -> ConversationDecision:
        """Handle user response during WAITING_FOR_CONFIRMATION."""
        affirmatives = ("yes", "yeah", "yep", "correct", "that's right", "do it", "sure", "ok", "okay", "confirm")
        negatives = ("no", "nope", "not that", "cancel", "don't", "don't do that", "never mind", "stop")

        if any(w in clean_text for w in affirmatives):
            intent = self._pending_intent or VoiceIntentType.NO_INTENT
            target = self._pending_target
            query = self._pending_query
            params = dict(self._pending_params)

            self._state = ConversationState.EXECUTING
            if target and target.lower() not in ("window", "app"):
                self._last_target = target.lower()
            self._last_intent = intent
            self._clear_pending_internal()

            return ConversationDecision(
                decision_type=DecisionType.EXECUTE,
                state=ConversationState.EXECUTING,
                message="Confirmed. Executing...",
                intent=intent,
                target=target,
                query=query,
                params=params,
                execute_action=True,
            )

        if any(w in clean_text for w in negatives):
            self._state = ConversationState.IDLE
            self._clear_pending_internal()
            return ConversationDecision(
                decision_type=DecisionType.CONFIRM,
                state=ConversationState.LISTENING,
                message="Okay, cancelled.",
                execute_action=False,
                cancelled=True,
            )

        return ConversationDecision(
            decision_type=DecisionType.CONFIRM,
            state=ConversationState.WAITING_FOR_CONFIRMATION,
            message=self._pending_question or "Sir, do you want me to proceed? Please say yes or no.",
            execute_action=False,
        )

    def _handle_clarification_turn(self, clean_text: str) -> ConversationDecision:
        """Handle user response during WAITING_FOR_CLARIFICATION."""
        negatives = ("no", "nope", "cancel", "don't", "never mind", "stop", "not that")
        affirmatives = ("yes", "yeah", "yep", "correct", "that's right", "sure", "ok", "okay")

        if any(w in clean_text for w in negatives):
            self._state = ConversationState.IDLE
            self._clear_pending_internal()
            return ConversationDecision(
                decision_type=DecisionType.CLARIFY,
                state=ConversationState.LISTENING,
                message="Okay. What would you like me to do?",
                execute_action=False,
                cancelled=True,
            )

        if any(w in clean_text for w in affirmatives) and self._pending_target:
            intent = self._pending_intent or VoiceIntentType.OPEN_APPLICATION
            target = self._pending_target
            self._state = ConversationState.EXECUTING
            self._last_target = target.lower()
            self._last_intent = intent
            self._clear_pending_internal()
            return ConversationDecision(
                decision_type=DecisionType.EXECUTE,
                state=ConversationState.EXECUTING,
                message=f"Opening {target.title()}...",
                intent=intent,
                target=target,
                execute_action=True,
            )

        for cand in self._pending_candidates:
            if cand.lower() in clean_text:
                intent = self._pending_intent or VoiceIntentType.OPEN_APPLICATION
                self._state = ConversationState.EXECUTING
                self._last_target = cand.lower()
                self._last_intent = intent
                self._clear_pending_internal()
                return ConversationDecision(
                    decision_type=DecisionType.EXECUTE,
                    state=ConversationState.EXECUTING,
                    message=f"Opening {cand.title()}...",
                    intent=intent,
                    target=cand,
                    execute_action=True,
                )

        return ConversationDecision(
            decision_type=DecisionType.CLARIFY,
            state=ConversationState.WAITING_FOR_CLARIFICATION,
            message=self._pending_question or "Sir, please clarify your choice.",
            execute_action=False,
        )

    def _is_destructive_action(self, clean_text: str, intent: VoiceIntentType, target: str | None) -> bool:
        """Check if request is potentially destructive or risky."""
        destructive_keywords = ("delete", "remove file", "format disk", "clear database", "erase")
        return any(kw in clean_text for kw in destructive_keywords)

    def _check_timeout_internal(self) -> None:
        if self._state in {ConversationState.WAITING_FOR_CONFIRMATION, ConversationState.WAITING_FOR_CLARIFICATION}:
            if time.time() - self._last_turn_time > self._timeout_seconds:
                logger.info("Conversation state timed out after %.1fs. Resetting to IDLE.", self._timeout_seconds)
                self._state = ConversationState.IDLE
                self._clear_pending_internal()

    def _clear_pending_internal(self) -> None:
        self._pending_intent = None
        self._pending_target = None
        self._pending_query = None
        self._pending_params = {}
        self._pending_question = None
        self._pending_candidates = []
        self._pending_reason = None
