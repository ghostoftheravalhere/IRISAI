"""Reasoning Service coordinating prompt building, provider generation, translation, and validation."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
import time
from typing import Any

from backend.brain.context_manager import ContextManager
from backend.brain.reasoning.events import (
    ReasoningCompletedEvent,
    ReasoningFailedEvent,
    ReasoningStartedEvent,
)
from backend.brain.reasoning.prompt_builder import PromptBuilder
from backend.brain.reasoning.provider import MockPlannerProvider, PlannerProvider
from backend.brain.reasoning.translator import PlanTranslator, PlanValidator
from backend.brain.skills.registry import SkillRegistry
from backend.brain.workflow import TaskPlan
from backend.core.events.bus import EventBus
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ReasoningResult:
    """Consolidated result of AI Reasoning plan generation."""

    success: bool
    plan: TaskPlan | None = None
    fallback_used: bool = False
    message: str = ""


class ReasoningService:
    """Coordinates prompt construction, LLM plan generation, translation, and validation."""

    def __init__(
        self,
        provider: PlannerProvider | None = None,
        skill_registry: SkillRegistry | None = None,
        context_manager: ContextManager | None = None,
        event_bus: EventBus | None = None,
        enabled: bool = True,
    ) -> None:
        self._provider = provider or MockPlannerProvider()
        self._skill_registry = skill_registry
        self._context_manager = context_manager
        self._event_bus = event_bus
        self._enabled = enabled
        self._lock = RLock()

    @property
    def enabled(self) -> bool:
        """Return whether reasoning service is active."""
        return self._enabled

    @property
    def provider(self) -> PlannerProvider:
        """Return active LLM planner provider."""
        return self._provider

    def generate_plan(self, user_command: str, session_id: str = "default") -> ReasoningResult:
        """Generate a validated TaskPlan for a natural language user command."""
        if not self._enabled:
            return ReasoningResult(
                success=False,
                plan=None,
                fallback_used=True,
                message="ReasoningService is disabled.",
            )

        t0 = time.time()
        provider_name = self._provider.name

        if self._event_bus:
            self._event_bus.publish(
                ReasoningStartedEvent(
                    user_prompt=user_command,
                    provider_name=provider_name,
                )
            )

        with self._lock:
            try:
                # 1. Discover Skill capabilities
                descriptors = self._skill_registry.discover_skills() if self._skill_registry else []
                # 2. Get session context
                session_ctx = (
                    self._context_manager.get_current_context(session_id) if self._context_manager else {}
                )
                # 3. Build Prompt
                prompt = PromptBuilder.build_prompt(user_command, descriptors, session_ctx)

                # 4. Generate raw LLM response
                raw_output = self._provider.generate_plan(prompt, session_ctx)

                # 5. Translate raw response to candidate TaskPlan
                candidate_plan = PlanTranslator.translate(raw_output)
                if not candidate_plan:
                    reason = "Failed to parse candidate plan from provider output."
                    logger.warning(reason)
                    if self._event_bus:
                        self._event_bus.publish(
                            ReasoningFailedEvent(
                                user_prompt=user_command,
                                reason=reason,
                                fallback_used=True,
                            )
                        )
                    return ReasoningResult(success=False, plan=None, fallback_used=True, message=reason)

                # 6. Validate candidate TaskPlan against SkillRegistry
                if self._skill_registry:
                    valid, reason = PlanValidator.validate_plan(candidate_plan, self._skill_registry)
                    if not valid:
                        logger.warning("Reasoning plan validation failed: %s", reason)
                        if self._event_bus:
                            self._event_bus.publish(
                                ReasoningFailedEvent(
                                    user_prompt=user_command,
                                    reason=reason,
                                    fallback_used=True,
                                )
                            )
                        return ReasoningResult(success=False, plan=None, fallback_used=True, message=reason)

                duration_ms = (time.time() - t0) * 1000.0
                if self._event_bus:
                    self._event_bus.publish(
                        ReasoningCompletedEvent(
                            user_prompt=user_command,
                            generated_steps_count=len(candidate_plan.steps),
                            latency_ms=duration_ms,
                        )
                    )

                return ReasoningResult(
                    success=True,
                    plan=candidate_plan,
                    fallback_used=False,
                    message="TaskPlan generated and validated successfully.",
                )
            except Exception as exc:
                logger.exception("ReasoningService plan generation failed")
                if self._event_bus:
                    self._event_bus.publish(
                        ReasoningFailedEvent(
                            user_prompt=user_command,
                            reason=str(exc),
                            fallback_used=True,
                        )
                    )
                return ReasoningResult(
                    success=False,
                    plan=None,
                    fallback_used=True,
                    message=f"Reasoning error: {exc}",
                )
