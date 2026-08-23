"""Central Brain Orchestrator and Safety Validation Subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
import time
from typing import Any, Protocol, Sequence

from backend.automation.dispatcher import AutomationDispatcher, AutomationResult
from backend.brain.context_manager import ContextManager
from backend.brain.events import (
    OrchestrationBlockedEvent,
    OrchestrationCompletedEvent,
    OrchestrationRequestedEvent,
)
from backend.brain.intent_manager import IntentManager
from backend.brain.workflow import TaskPlan, WorkflowStep
from backend.core.events.bus import EventBus
from backend.utils.logger import get_logger
from backend.voice.command_parser import IntentParserService, VoiceIntent, VoiceIntentType

logger = get_logger(__name__)


@dataclass(frozen=True)
class OrchestrationRequest:
    """Encapsulates an incoming intent orchestration request."""

    source: str
    intent: VoiceIntent
    raw_transcript: str = ""


@dataclass(frozen=True)
class OrchestrationResponse:
    """Encapsulates the consolidated outcome of brain orchestration."""

    intent: str
    status: str
    message: str
    success: bool
    action_result: AutomationResult | None = None


class SafetyPolicy(Protocol):
    """Protocol for modular safety and policy validation rules."""

    def validate(self, request: OrchestrationRequest) -> tuple[bool, str]:
        """Validate request; return (is_allowed, reason)."""
        ...


@dataclass(frozen=True)
class AllowAllSafetyPolicy:
    """Baseline safety policy allowing all valid commands."""

    def validate(self, request: OrchestrationRequest) -> tuple[bool, str]:
        """Allow all intent requests by default."""
        return True, "Allowed by default safety policy."


@dataclass
class RateLimitSafetyPolicy:
    """Prevents duplicate execution of identical commands within a cooldown window."""

    cooldown_seconds: float = 0.3
    _last_execution: dict[str, float] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def validate(self, request: OrchestrationRequest) -> tuple[bool, str]:
        """Check if request violates minimum execution cooldown."""
        intent_name = request.intent.intent.value
        now = time.time()
        with self._lock:
            last = self._last_execution.get(intent_name, 0.0)
            if now - last < self.cooldown_seconds:
                return False, f"Rate limit: command '{intent_name}' repeated within {self.cooldown_seconds}s."
            self._last_execution[intent_name] = now
            return True, "Rate limit check passed."


class BrainOrchestrator:
    """Central decision-making controller routing perception intents to execution."""

    def __init__(
        self,
        intent_manager: IntentManager,
        context_manager: ContextManager,
        automation_dispatcher: AutomationDispatcher,
        event_bus: EventBus | None = None,
        safety_policies: Sequence[SafetyPolicy] | None = None,
        workflow_engine: Any | None = None,
        reasoning_service: Any | None = None,
        dialogue_manager: Any | None = None,
        canonical_action_engine: Any | None = None,
        agent_core: Any | None = None,
        enabled: bool = True,
    ) -> None:
        self._intent_manager = intent_manager
        self._context_manager = context_manager
        self._automation_dispatcher = automation_dispatcher
        self._event_bus = event_bus
        if safety_policies is not None:
            self._safety_policies = list(safety_policies)
        else:
            self._safety_policies = [AllowAllSafetyPolicy()]
        self._workflow_engine = workflow_engine
        self._reasoning_service = reasoning_service
        self._dialogue_manager = dialogue_manager
        self._canonical_action_engine = canonical_action_engine
        self._agent_core = agent_core
        self._enabled = enabled
        self._lock = RLock()

    @property
    def enabled(self) -> bool:
        """Return whether the orchestrator is active."""
        return self._enabled

    def _should_use_agent_core(self, request: OrchestrationRequest) -> tuple[bool, str]:
        """Determine if request should be routed to AgentCore rather than simple ActionEngine path."""
        if self._agent_core is None:
            return False, "AgentCore not configured"

        # 0. Preserve active dialogue state turns (confirmations, clarifications, ordinal selection)
        if self._dialogue_manager is not None:
            dm_state = getattr(self._dialogue_manager, "state", None)
            state_val = getattr(dm_state, "value", str(dm_state))
            if state_val != "IDLE":
                return False, f"Pending dialogue turn active ({state_val})"

        raw_text = (request.raw_transcript or request.intent.text or "").lower().strip()
        intent_type = request.intent.intent

        # 1. Unmatched phrases or search intents
        if intent_type in (VoiceIntentType.NO_INTENT, VoiceIntentType.BROWSER_SEARCH):
            return True, f"{intent_type.value} routed to AgentCore"

        # 2. Compound conjunctions ("and then", "and type", "and write", "and tell", "and search")
        compound_patterns = [" and ", " and then ", " then ", " and type ", " and write ", " and search ", " and summarize "]
        for pat in compound_patterns:
            if pat in raw_text:
                return True, f"Compound conjunction '{pat.strip()}' detected"

        # 3. Agentic / Multi-step intent keywords
        agentic_keywords = [
            "check", "find", "search online", "search the web", "summarize",
            "explain", "compare", "inspect", "locate", "tell me", "show me",
            "what completed", "what changed", "which files", "github repository",
            "delete file", "read document", "summarize it"
        ]
        for kw in agentic_keywords:
            if kw in raw_text:
                return True, f"Agentic keyword '{kw}' detected"

        # 4. Single intent parsed with compound target (e.g. target="notepad and type hello")
        target_str = str(request.intent.target or "").lower()
        if " and " in target_str or " type " in target_str:
            return True, "Compound target phrase detected"

        return False, "Simple deterministic command"

    def execute_task_plan(self, plan: Any) -> bool:
        """Execute a multi-step TaskPlan via WorkflowEngine."""
        if self._workflow_engine is not None:
            return self._workflow_engine.execute_plan(plan)
        return False

    def reason_and_execute(self, user_command: str) -> bool:
        """Generate an AI reasoning plan and execute it via WorkflowEngine."""
        if self._reasoning_service is not None:
            res = self._reasoning_service.generate_plan(user_command)
            if res.success and res.plan:
                return self.execute_task_plan(res.plan)
        return False

    def process_fusion_result(self, fusion_result: Any, source: str = "multimodal") -> OrchestrationResponse:
        """Process a unified Multimodal FusionResult."""
        target = getattr(fusion_result, "target", None)
        query = getattr(fusion_result, "query", None)
        params = getattr(fusion_result, "params", {}) or {}
        raw_text = getattr(fusion_result, "raw_text", "") or getattr(fusion_result, "unified_intent", "")
        intent_str = getattr(fusion_result, "unified_intent", "NO_INTENT")

        # Resolve intent enum or fallback
        intent_enum = VoiceIntentType.NO_INTENT
        for member in VoiceIntentType:
            if member.value == intent_str:
                intent_enum = member
                break

        intent = VoiceIntent(intent=intent_enum, text=raw_text, target=target, query=query, params=params)
        req = OrchestrationRequest(source=source, intent=intent, raw_transcript=raw_text)
        return self.process_intent(req)

    def process_intent(self, request: OrchestrationRequest) -> OrchestrationResponse:
        """Validate, record, and route an orchestration request to execution."""
        intent_name = request.intent.intent.value
        t0 = time.time()

        if self._event_bus:
            self._event_bus.publish(
                OrchestrationRequestedEvent(
                    source=request.source,
                    intent=intent_name,
                    raw_payload=request.raw_transcript,
                )
            )

        if not self._enabled:
            # Fallback direct dispatch if orchestrator is disabled
            res = self._automation_dispatcher.dispatch(request.intent)
            return OrchestrationResponse(
                intent=res.intent.value,
                status="SUCCESS" if res.success else "ERROR",
                message=res.message,
                success=res.success,
                action_result=res,
            )

        with self._lock:
            # 1. Evaluate Safety Policies
            for policy in self._safety_policies:
                allowed, reason = policy.validate(request)
                if not allowed:
                    logger.warning("Orchestrator blocked intent '%s': %s", intent_name, reason)
                    if self._event_bus:
                        self._event_bus.publish(
                            OrchestrationBlockedEvent(
                                intent=intent_name,
                                reason=reason,
                                policy_name=policy.__class__.__name__,
                            )
                        )
                    return OrchestrationResponse(
                        intent=intent_name,
                        status="BLOCKED",
                        message=reason,
                        success=False,
                    )

            # 2. Check if request should route to AgentCore
            should_agent, reason = self._should_use_agent_core(request)
            if should_agent and self._agent_core is not None:
                raw_goal = request.raw_transcript or request.intent.text or ""
                logger.info("BrainOrchestrator routing goal to AgentCore: '%s' (reason: %s)", raw_goal, reason)
                agent_res = self._agent_core.process_goal(raw_goal)
                if agent_res.error_code == "CONFIRMATION_REQUIRED":
                    if self._dialogue_manager is not None:
                        setattr(self._dialogue_manager, "_pending_action", agent_res.task_state)
                        setattr(self._dialogue_manager, "_state", "AWAITING_CONFIRMATION")
                    return OrchestrationResponse(
                        intent="AGENT_CORE",
                        status="WAITING_CONFIRMATION",
                        message=agent_res.response,
                        success=False,
                    )
                return OrchestrationResponse(
                    intent="AGENT_CORE",
                    status="SUCCESS" if agent_res.success else "ERROR",
                    message=agent_res.response,
                    success=agent_res.success,
                )

            # 3. Dispatch Automation or Multi-step Workflow
            if request.intent.intent == VoiceIntentType.BROWSER_SEARCH and self._workflow_engine is not None and self._workflow_engine.enabled:
                target_app = request.intent.target or "chrome"
                search_query = (
                    request.intent.query
                    or IntentParserService._sanitize_search_query(request.intent.text)
                    or request.intent.text
                )
                hotkey_keys = ["ctrl", "f"] if target_app == "settings" else ["ctrl", "l"]
                plan = TaskPlan(
                    name=f"Application Search '{search_query}' in {target_app}",
                    steps=[
                        WorkflowStep(intent="OPEN_APPLICATION", target=target_app),
                        WorkflowStep(intent="WAIT_FOR_WINDOW", target=target_app, params={"timeout_sec": 3.0}),
                        WorkflowStep(intent="ACTIVATE_WINDOW", target=target_app),
                        WorkflowStep(intent="VERIFY_WINDOW_ACTIVE", target=target_app),
                        WorkflowStep(intent="HOTKEY", target=target_app, params={"keys": hotkey_keys}),
                        WorkflowStep(intent="TYPE_TEXT", target=target_app, params={"text": search_query, "query": search_query}),
                        WorkflowStep(intent="PRESS_KEY", target=target_app, params={"key": "enter"}),
                    ],
                )
                success = self._workflow_engine.execute_plan(plan)
                result = AutomationResult(
                    success=success,
                    intent=request.intent.intent,
                    message=f"Executed browser search TaskPlan for '{search_query}' in {target_app}",
                )
            elif self._dialogue_manager is not None:
                action_req = (
                    self._canonical_action_engine.from_voice_intent(request.intent)
                    if self._canonical_action_engine is not None
                    else None
                )
                logger.info("Orchestrator dialogue routing: action_req=%s", action_req)
                g_x = request.intent.params.get("gaze_x") if request.intent.params else None
                g_y = request.intent.params.get("gaze_y") if request.intent.params else None

                turn_res = self._dialogue_manager.process_utterance(
                    text=request.raw_transcript or request.intent.text,
                    voice_request=action_req,
                    gaze_x=g_x,
                    gaze_y=g_y,
                )

                if turn_res.prompt_message and not (turn_res.executed_result and turn_res.executed_result.success):
                    result = AutomationResult(
                        success=True,
                        intent=request.intent.intent,
                        message=turn_res.prompt_message,
                    )
                elif turn_res.executed_result and turn_res.executed_result.success:
                    result = AutomationResult(
                        success=True,
                        intent=request.intent.intent,
                        message=turn_res.executed_result.message,
                    )
                elif turn_res.cancelled:
                    result = AutomationResult(
                        success=True,
                        intent=request.intent.intent,
                        message="Action cancelled.",
                    )
                else:
                    result = self._automation_dispatcher.dispatch(request.intent)
            else:
                result = self._automation_dispatcher.dispatch(request.intent)

            latency_ms = (time.time() - t0) * 1000.0

            # 3. Record Session Context & Intent State
            try:
                if hasattr(self._intent_manager, "record_intent"):
                    self._intent_manager.record_intent(request.intent)
                if hasattr(self._context_manager, "record_utterance"):
                    self._context_manager.record_utterance(
                        transcript=request.raw_transcript,
                        intent=intent_name,
                        status=result.message,
                    )
            except Exception:
                logger.exception("Context/Intent state recording failed.")

            if self._event_bus:
                self._event_bus.publish(
                    OrchestrationCompletedEvent(
                        intent=result.intent.value,
                        action=result.intent.value,
                        success=result.success,
                        execution_message=result.message,
                        latency_ms=latency_ms,
                    )
                )

            return OrchestrationResponse(
                intent=result.intent.value,
                status="SUCCESS" if result.success else "ERROR",
                message=result.message,
                success=result.success,
                action_result=result,
            )
