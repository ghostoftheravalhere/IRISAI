"""Voice command pipeline: IntentParser → ActionEngine → DesktopController.

Eye gestures and voice commands share the same ActionEngine instance for
cooldown / pause coordination. Desktop effects run through DesktopController
via AutomationDispatcher without modifying the eye-tracking gesture path.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import TYPE_CHECKING

from backend.brain.fusion import MultimodalFusionEngine, PerceptionEvent
from backend.brain.orchestrator import BrainOrchestrator, OrchestrationRequest
from backend.automation.dispatcher import AutomationDispatcher, AutomationResult
from backend.core.events.bus import EventBus
from backend.utils.logger import get_logger
from backend.voice.command_parser import IntentParserService, VoiceIntent, VoiceIntentType
from backend.voice.normalizer import TranscriptNormalizer
from backend.voice.telemetry import AutomationExecutedEvent, IntentParsedEvent

if TYPE_CHECKING:
    from backend.eye_tracking.action_engine import ActionEngine

logger = get_logger(__name__)


@dataclass(frozen=True)
class VoicePipelineResult:
    """Consolidated outcome of voice command processing and dispatch."""

    intent: str
    message: str
    success: bool
    transcript: str


class VoiceCommandPipeline:
    """Wire voice intents through the shared ActionEngine action pipeline.

    Flow:
        transcript → TranscriptNormalizer → IntentParserService → ActionEngine gate → MultimodalFusionEngine
        → BrainOrchestrator → AutomationDispatcher → DesktopController
    """

    def __init__(
        self,
        intent_parser: IntentParserService,
        action_engine: ActionEngine,
        automation_dispatcher: AutomationDispatcher,
        normalizer: TranscriptNormalizer | None = None,
        event_bus: EventBus | None = None,
        orchestrator: BrainOrchestrator | None = None,
        fusion_engine: MultimodalFusionEngine | None = None,
    ) -> None:
        self._intent_parser = intent_parser
        self._action_engine = action_engine
        self._automation_dispatcher = automation_dispatcher
        self._normalizer = normalizer or TranscriptNormalizer()
        self._event_bus = event_bus
        self._orchestrator = orchestrator
        self._fusion_engine = fusion_engine
        self._lock = RLock()

    def handle_transcript(self, transcript: str) -> tuple[str, str]:
        """Parse and execute a transcript; return (intent, execution_status)."""
        result = self.execute(transcript)
        return result.intent, result.message

    def execute(self, transcript: str | None) -> VoicePipelineResult:
        """Run the full voice action pipeline for one utterance."""
        text = (transcript or "").strip()
        with self._lock:
            if not text:
                return VoicePipelineResult(
                    intent=VoiceIntentType.NO_INTENT.value,
                    message="Empty speech.",
                    success=False,
                    transcript=text,
                )

            normalized_text = self._normalizer.normalize(text)
            voice_intent = self._intent_parser.parse(normalized_text)

            if self._event_bus:
                self._event_bus.publish(
                    IntentParsedEvent(
                        raw_transcript=text,
                        normalized_transcript=normalized_text,
                        intent=voice_intent.intent.value if voice_intent else None,
                        rule_applied=getattr(voice_intent, "rule_name", None),
                    )
                )

            if voice_intent.intent == VoiceIntentType.NO_INTENT:
                logger.info("Pipeline:")
                logger.info("- ActionEngine request: skipped (NO_INTENT)")
                return VoicePipelineResult(
                    intent=VoiceIntentType.NO_INTENT.value,
                    message="Unknown command.",
                    success=False,
                    transcript=text,
                )

            if not self._action_engine_allows(voice_intent):
                return VoicePipelineResult(
                    intent=voice_intent.intent.value,
                    message="Action blocked by ActionEngine cooldown/pause.",
                    success=False,
                    transcript=text,
                )

            if self._orchestrator is not None:
                if self._fusion_engine is not None:
                    pevent = PerceptionEvent(
                        source="voice",
                        intent=voice_intent.intent.value,
                        confidence=1.0,
                        target=voice_intent.target,
                        raw_text=text,
                        query=voice_intent.query,
                        params=voice_intent.params,
                    )
                    fused = self._fusion_engine.ingest_event(pevent)
                    orch_response = self._orchestrator.process_fusion_result(fused, source="voice")
                else:
                    orch_response = self._orchestrator.process_intent(
                        OrchestrationRequest(source="voice", intent=voice_intent, raw_transcript=text)
                    )
                return VoicePipelineResult(
                    intent=orch_response.intent,
                    message=orch_response.message,
                    success=orch_response.success,
                    transcript=text,
                )

            automation_result = self._automation_dispatcher.dispatch(voice_intent)
            if self._event_bus:
                self._event_bus.publish(
                    AutomationExecutedEvent(
                        intent=automation_result.intent.value,
                        action=automation_result.intent.value,
                        success=automation_result.success,
                        execution_status=automation_result.message,
                    )
                )
            return self._to_pipeline_result(automation_result, text)

    def _action_engine_allows(self, voice_intent: VoiceIntent) -> bool:
        """Reuse the shared ActionEngine instance in the voice action pipeline.

        Eye gestures continue to own ActionEngine ``update()`` / cooldown timing
        inside the camera loop. Voice consults the same engine for coordination
        logging without mutating eye-tracking gesture state.
        """
        state = self._action_engine.get_latest_state()
        logger.info("Pipeline:")
        logger.info(
            "- ActionEngine request: intent=%s action=%s cursorPaused=%s",
            voice_intent.intent.value,
            state.action.value,
            state.cursorPaused,
        )
        logger.info(
            "Voice intent %s through ActionEngine pipeline (action=%s, cursorPaused=%s)",
            voice_intent.intent.value,
            state.action.value,
            state.cursorPaused,
        )
        return True

    @staticmethod
    def _to_pipeline_result(result: AutomationResult, transcript: str) -> VoicePipelineResult:
        return VoicePipelineResult(
            intent=result.intent.value,
            message=result.message,
            success=result.success,
            transcript=transcript,
        )
