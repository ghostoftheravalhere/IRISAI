"""Conversational DialogueManager state machine for turn-taking, confirmation, and clarification."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
import time
from typing import Any, Callable

from backend.automation.action_engine import ActionEngine
from backend.automation.action_models import ActionRequest, ActionResult, CanonicalAction
from backend.perception.ambiguity_engine import AmbiguityEngine, AmbiguityResolution, CandidateMatch
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class DialogueState(str, Enum):
    """Dialogue state machine states."""

    IDLE = "IDLE"
    PROCESSING_INPUT = "PROCESSING_INPUT"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    AWAITING_CLARIFICATION = "AWAITING_CLARIFICATION"
    EXECUTING = "EXECUTING"


@dataclass
class DialogueTurnResult:
    """Outcome of a dialogue processing turn."""

    state: DialogueState
    prompt_message: str | None = None
    executed_result: ActionResult | None = None
    cancelled: bool = False
    timed_out: bool = False


class DialogueManager:
    """Manages multi-turn conversation, pending action confirmation, and ambiguity clarification."""

    def __init__(
        self,
        action_engine: ActionEngine,
        ambiguity_engine: AmbiguityEngine | None = None,
        agent_core: Any | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._action_engine = action_engine
        self._ambiguity_engine = ambiguity_engine or AmbiguityEngine()
        self._agent_core = agent_core
        self._timeout_seconds = timeout_seconds

        self._state = DialogueState.IDLE
        self._pending_request: ActionRequest | None = None
        self._pending_action: Any | None = None
        self._pending_prompt: str | None = None
        self._candidates: list[CandidateMatch] = []
        self._last_resolved_target: str | None = None
        self._last_active_app: str | None = None
        self._last_turn_time: float = time.time()
        self._lock = RLock()

    @property
    def state(self) -> DialogueState:
        with self._lock:
            self._check_timeout_internal()
            return self._state

    def process_utterance(
        self,
        text: str,
        voice_request: ActionRequest | None = None,
        active_app: str | None = None,
        gaze_x: float | None = None,
        gaze_y: float | None = None,
    ) -> DialogueTurnResult:
        """Process an incoming voice utterance or command through dialogue state machine."""
        with self._lock:
            self._check_timeout_internal()
            clean_text = (text or "").strip().lower()
            if active_app:
                self._last_active_app = active_app

            # Handle pending state dialogue responses
            if self._state == DialogueState.AWAITING_CONFIRMATION:
                return self._handle_confirmation_response(clean_text)

            if self._state == DialogueState.AWAITING_CLARIFICATION:
                return self._handle_clarification_response(clean_text)

            # New input processing
            self._state = DialogueState.PROCESSING_INPUT
            req = voice_request or ActionRequest(action=CanonicalAction.NO_ACTION, text_payload=text)

            # Resolve referential pronouns ("it", "this", "that", "the previous one", "that chat", "that window")
            if req.target_phrase and req.target_phrase.lower() in {"it", "this", "that", "here", "there", "the previous one", "that chat", "that window", "this button"}:
                resolved = self._last_resolved_target or active_app or self._last_active_app
                if resolved:
                    req = ActionRequest(
                        action=req.action,
                        source_modality=req.source_modality,
                        target_phrase=resolved,
                        target_x=req.target_x,
                        target_y=req.target_y,
                        text_payload=req.text_payload,
                        params=req.params,
                    )

            # Check for target ambiguity if a named target phrase is present and spatial coordinates are not provided
            if req.target_phrase and req.target_x is None and req.target_y is None and not req.target_phrase.startswith("Point("):
                res = self._ambiguity_engine.resolve_candidates(
                    target_phrase=req.target_phrase,
                    active_app=active_app or self._last_active_app,
                    gaze_x=gaze_x,
                    gaze_y=gaze_y,
                )

                if res.classification == "MULTIPLE_CANDIDATES":
                    self._state = DialogueState.AWAITING_CLARIFICATION
                    self._pending_request = req
                    self._candidates = list(res.candidates)
                    self._pending_prompt = res.prompt_message
                    self._last_turn_time = time.time()
                    return DialogueTurnResult(DialogueState.AWAITING_CLARIFICATION, prompt_message=res.prompt_message)

                if res.classification == "MEDIUM_CONFIDENCE":
                    self._state = DialogueState.AWAITING_CONFIRMATION
                    best_label = res.best_candidate.label if res.best_candidate else req.target_phrase
                    # Update target coords from best match
                    if res.best_candidate:
                        req = ActionRequest(
                            action=req.action,
                            source_modality=req.source_modality,
                            target_phrase=res.best_candidate.label,
                            target_x=res.best_candidate.x,
                            target_y=res.best_candidate.y,
                            text_payload=req.text_payload,
                            params=req.params,
                        )
                    self._pending_request = req
                    self._pending_prompt = res.prompt_message or f"I found '{best_label}'. Do you want me to open it?"
                    self._last_turn_time = time.time()
                    return DialogueTurnResult(DialogueState.AWAITING_CONFIRMATION, prompt_message=self._pending_prompt)

                if res.classification == "HIGH_CONFIDENCE" and res.best_candidate:
                    req = ActionRequest(
                        action=req.action,
                        source_modality=req.source_modality,
                        target_phrase=res.best_candidate.label,
                        target_x=res.best_candidate.x,
                        target_y=res.best_candidate.y,
                        text_payload=req.text_payload,
                        params=req.params,
                    )

            # Direct action execution for high-confidence/unambiguous/direct requests
            self._state = DialogueState.EXECUTING
            if req.target_phrase:
                self._last_resolved_target = req.target_phrase
            result = self._action_engine.execute(req)
            self._reset_state()
            return DialogueTurnResult(DialogueState.IDLE, executed_result=result)

    def confirm_pending(self) -> DialogueTurnResult:
        """Explicitly confirm pending action."""
        with self._lock:
            if self._pending_action is not None and hasattr(self._pending_action, "user_goal"):
                task_state = self._pending_action
                self._reset_state()
                if self._agent_core is not None:
                    agent_res = self._agent_core.resume_task_with_confirmation(task_state, confirmed=True)
                    exec_res = ActionResult(agent_res.success, CanonicalAction.NO_ACTION, agent_res.response)
                    return DialogueTurnResult(DialogueState.IDLE, executed_result=exec_res, prompt_message=agent_res.response)
                exec_res = ActionResult(True, CanonicalAction.NO_ACTION, "Task confirmed.")
                return DialogueTurnResult(DialogueState.IDLE, executed_result=exec_res)

            if not self._pending_request:
                self._reset_state()
                return DialogueTurnResult(DialogueState.IDLE)

            self._state = DialogueState.EXECUTING
            req = self._pending_request
            if req.target_phrase:
                self._last_resolved_target = req.target_phrase
            result = self._action_engine.execute(req)
            self._reset_state()
            return DialogueTurnResult(DialogueState.IDLE, executed_result=result)

    def cancel_pending(self) -> DialogueTurnResult:
        """Cancel pending action or dialogue turn."""
        with self._lock:
            if self._pending_action is not None and hasattr(self._pending_action, "user_goal"):
                task_state = self._pending_action
                self._reset_state()
                if self._agent_core is not None:
                    agent_res = self._agent_core.resume_task_with_confirmation(task_state, confirmed=False)
                    exec_res = ActionResult(False, CanonicalAction.NO_ACTION, agent_res.response)
                    return DialogueTurnResult(DialogueState.IDLE, executed_result=exec_res, cancelled=True, prompt_message=agent_res.response)
                return DialogueTurnResult(DialogueState.IDLE, cancelled=True, prompt_message="Action cancelled.")

            self._reset_state()
            return DialogueTurnResult(DialogueState.IDLE, cancelled=True, prompt_message="Action cancelled.")

    def _handle_confirmation_response(self, text: str) -> DialogueTurnResult:
        if any(w in text for w in ["yes", "yeah", "yep", "sure", "do it", "confirm", "ok", "okay"]):
            return self.confirm_pending()
        if any(w in text for w in ["no", "nope", "cancel", "don't", "never mind", "stop"]):
            return self.cancel_pending()

        prompt = f"Please confirm: {self._pending_prompt}"
        return DialogueTurnResult(DialogueState.AWAITING_CONFIRMATION, prompt_message=prompt)

    def _handle_clarification_response(self, text: str) -> DialogueTurnResult:
        if any(w in text for w in ["no", "cancel", "never mind", "stop"]):
            return self.cancel_pending()

        tokens = set(text.split())
        chosen_index: int | None = None
        if any(term in text for term in ["second", "2nd", "option 2", "number 2", "the 2nd", "two"]) or "2" in tokens:
            chosen_index = 1
        elif any(term in text for term in ["third", "3rd", "option 3", "number 3", "the 3rd", "three"]) or "3" in tokens:
            chosen_index = 2
        elif any(term in text for term in ["first", "1st", "option 1", "number 1", "the 1st", "one"]) or "1" in tokens:
            chosen_index = 0

        if chosen_index is not None and chosen_index < len(self._candidates):
            candidate = self._candidates[chosen_index]
            base_req = self._pending_request or ActionRequest(action=CanonicalAction.OPEN_APPLICATION)
            resolved_req = ActionRequest(
                action=base_req.action,
                source_modality=base_req.source_modality,
                target_phrase=candidate.label,
                target_x=candidate.x,
                target_y=candidate.y,
                text_payload=base_req.text_payload,
                params=base_req.params,
            )
            self._state = DialogueState.EXECUTING
            self._last_resolved_target = candidate.label
            res = self._action_engine.execute(resolved_req)
            self._reset_state()
            return DialogueTurnResult(DialogueState.IDLE, executed_result=res)

        prompt = self._pending_prompt or "Which candidate would you like to select?"
        return DialogueTurnResult(DialogueState.AWAITING_CLARIFICATION, prompt_message=prompt)

    def _check_timeout_internal(self) -> bool:
        if self._state in {DialogueState.AWAITING_CONFIRMATION, DialogueState.AWAITING_CLARIFICATION}:
            if time.time() - self._last_turn_time > self._timeout_seconds:
                logger.info("Dialogue turn timed out after %.1fs. Resetting state.", self._timeout_seconds)
                self._reset_state()
                return True
        return False

    def _reset_state(self) -> None:
        self._state = DialogueState.IDLE
        self._pending_request = None
        self._pending_prompt = None
        self._candidates = []
        self._last_turn_time = time.time()
