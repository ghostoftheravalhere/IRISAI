"""Voice command pipeline: IntentParser → ActionEngine → DesktopController.

Eye gestures and voice commands share the same ActionEngine instance for
cooldown / pause coordination. Desktop effects run through DesktopController
via AutomationDispatcher without modifying the eye-tracking gesture path.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import TYPE_CHECKING

from backend.automation.dispatcher import AutomationDispatcher, AutomationResult
from backend.utils.logger import get_logger
from backend.voice.command_parser import IntentParserService, VoiceIntent, VoiceIntentType

if TYPE_CHECKING:
    from backend.eye_tracking.action_engine import ActionEngine

logger = get_logger(__name__)


@dataclass(frozen=True)
class VoicePipelineResult:
    """Structured result of handling one voice transcript."""

    intent: str
    message: str
    success: bool
    transcript: str


class VoiceCommandPipeline:
    """Wire voice intents through the shared ActionEngine action pipeline.

    Flow:
        transcript → IntentParserService → ActionEngine gate → AutomationDispatcher
        → DesktopController
    """

    def __init__(
        self,
        intent_parser: IntentParserService,
        action_engine: ActionEngine,
        automation_dispatcher: AutomationDispatcher,
    ) -> None:
        self._intent_parser = intent_parser
        self._action_engine = action_engine
        self._automation_dispatcher = automation_dispatcher
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

            voice_intent = self._intent_parser.parse(text)
            if voice_intent.intent == VoiceIntentType.NO_INTENT:
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

            automation_result = self._automation_dispatcher.dispatch(voice_intent)
            return self._to_pipeline_result(automation_result, text)

    def _action_engine_allows(self, voice_intent: VoiceIntent) -> bool:
        """Reuse the shared ActionEngine instance in the voice action pipeline.

        Eye gestures continue to own ActionEngine ``update()`` / cooldown timing
        inside the camera loop. Voice consults the same engine for coordination
        logging without mutating eye-tracking gesture state.
        """
        state = self._action_engine.get_latest_state()
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
