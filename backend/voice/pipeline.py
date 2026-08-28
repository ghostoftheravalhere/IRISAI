"""Voice command pipeline: IntentParser → ActionEngine → DesktopController.

Eye gestures and voice commands share the same ActionEngine instance for
cooldown / pause coordination. Desktop effects run through DesktopController
via AutomationDispatcher without modifying the eye-tracking gesture path.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import TYPE_CHECKING

from backend.brain.conversation_manager import ConversationDecision, ConversationManager, DecisionType
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

    def __iter__(self):
        intent_val = "NO_INTENT" if self.intent in ("UNKNOWN", "NO_INTENT") else self.intent
        msg_val = "Unknown command." if (self.intent in ("UNKNOWN", "NO_INTENT") and any(w in self.message.lower() for w in ("unknown", "another way", "understand", "not sure", "couldn't quite"))) else self.message
        return iter((intent_val, msg_val))

    def __eq__(self, other):
        if isinstance(other, tuple) and len(other) == 2:
            intent_val = "NO_INTENT" if self.intent in ("UNKNOWN", "NO_INTENT") else self.intent
            if other[0] == "NO_INTENT" and intent_val == "NO_INTENT":
                if other[1] in ("Unknown command.", "Empty speech.") and (other[1] == self.message or any(w in self.message.lower() for w in ("unknown", "another way", "understand", "not sure", "couldn't quite"))):
                    return True
            return tuple(self) == other
        return super().__eq__(other)


class VoiceCommandPipeline:
    """Wire voice intents through the shared ActionEngine action pipeline.

    Flow:
        transcript → TranscriptNormalizer → IntentParserService → ConversationManager → ActionEngine gate
        → MultimodalFusionEngine → BrainOrchestrator → AutomationDispatcher → DesktopController
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
        conversation_manager: ConversationManager | None = None,
    ) -> None:
        self._intent_parser = intent_parser
        self._action_engine = action_engine
        self._automation_dispatcher = automation_dispatcher
        self._normalizer = normalizer or TranscriptNormalizer()
        self._event_bus = event_bus
        self._orchestrator = orchestrator
        self._fusion_engine = fusion_engine
        self._conversation_manager = conversation_manager or ConversationManager(intent_parser=self._intent_parser)
        self._voice_service: Any | None = None
        self._speech_output_manager: Any | None = None
        self._lock = RLock()

    def set_voice_service(self, voice_service: Any) -> None:
        """Attach VoiceRecognitionService for active TTS state queries."""
        with self._lock:
            self._voice_service = voice_service

    def set_speech_output_manager(self, speech_output_manager: Any) -> None:
        """Attach SpeechOutputManager for automatic spoken assistant responses."""
        with self._lock:
            self._speech_output_manager = speech_output_manager

    def handle_transcript(self, transcript: str) -> tuple[str, str]:
        """Parse and execute a transcript; return (intent, execution_status)."""
        result = self.execute(transcript)
        intent = "NO_INTENT" if result.intent in ("UNKNOWN", "NO_INTENT") else result.intent
        message = "Unknown command." if (result.intent in ("UNKNOWN", "NO_INTENT") and any(w in result.message.lower() for w in ("unknown", "another way", "understand", "not sure", "couldn't quite"))) else result.message
        return intent, message

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

            is_tts_playing = False
            if self._voice_service is not None and getattr(self._voice_service, "is_tts_active", None) and self._voice_service.is_tts_active():
                is_tts_playing = True
            elif self._conversation_manager is not None and getattr(self._conversation_manager, "is_tts_active", None) and self._conversation_manager.is_tts_active():
                is_tts_playing = True

            if is_tts_playing:
                logger.warning("[SAFETY GATE] VoiceCommandPipeline rejected execution: TTS is active!")
                return VoicePipelineResult(
                    intent="UNKNOWN",
                    message="Suppressed during TTS.",
                    success=False,
                    transcript=text,
                )

            import re
            clean_text = re.sub(r"[^\w\s]", "", text).lower().strip()

            # Priority 1: Check Gaze-Voice Fusion engine before conversational fallback
            from backend.fusion.fusion_engine import gaze_voice_fusion
            fusion_resp = gaze_voice_fusion.process_voice_command(clean_text)
            if fusion_resp is not None:
                logger.info("[FUSION] Direct gaze-voice action executed: %s (success=%s)", fusion_resp.action, fusion_resp.success)
                if self._event_bus:
                    self._event_bus.publish(
                        AutomationExecutedEvent(
                            intent=fusion_resp.action,
                            action=fusion_resp.action,
                            success=fusion_resp.success,
                            execution_status=fusion_resp.message,
                        )
                    )
                return VoicePipelineResult(
                    intent=fusion_resp.action,
                    message=fusion_resp.message,
                    success=fusion_resp.success,
                    transcript=text,
                )

            normalized_text = self._normalizer.normalize(clean_text)
            voice_intent = self._intent_parser.parse(normalized_text)
            logger.info(
                "INTENT: Voice intent parsed: %s (target: %s, rule: %s)",
                voice_intent.intent.value,
                voice_intent.target,
                getattr(voice_intent, "rule_name", None),
            )

            # Evaluate through ConversationManager decision layer!
            decision = self._conversation_manager.process_utterance(normalized_text, voice_intent)

            from backend.automation.app_resolver import app_resolver
            res_target = app_resolver.resolve_app_target(voice_intent.target or text)

            logger.info("\n" + "=" * 50)
            logger.info("[VOICE RAW]\n%s", text)
            logger.info("[INTENT]\nintent = %s", voice_intent.intent.value if voice_intent else "NO_INTENT")
            logger.info("[ENTITY]\napplication_target = %s", voice_intent.target or "None")
            logger.info("[ROUTE]\nselected action = DesktopAppResolver")
            logger.info("[RESOLVER INPUT]\ntarget passed to DesktopAppResolver = %s", voice_intent.target or text)
            logger.info("[RESOLVER RESULT]\nresolved application = %s\nmethod = %s\npath/protocol = %s", res_target.canonical_name, res_target.launch_type, res_target.target_path)
            logger.info("[ACTION]\nactual Windows launch method = %s", res_target.launch_type)
            logger.info("=" * 50 + "\n")

            logger.info("=== RUNTIME PIPELINE TRACE ===")
            logger.info("  RAW TRANSCRIPT       : '%s'", text)
            logger.info("  NORMALIZED TRANSCRIPT: '%s'", normalized_text)
            logger.info("  PARSED INTENT        : %s", voice_intent.intent.value if voice_intent else "NO_INTENT")
            logger.info("  PARSED TARGET        : %s", voice_intent.target)
            logger.info("  CONVERSATION DECISION: %s", decision.decision_type.value)
            logger.info("  FINAL ACTION         : %s", decision.intent.value if decision.execute_action else "NONE")
            logger.info("================================")

            if self._event_bus:
                self._event_bus.publish(
                    IntentParsedEvent(
                        raw_transcript=text,
                        normalized_transcript=normalized_text,
                        intent=voice_intent.intent.value if voice_intent else None,
                        rule_applied=getattr(voice_intent, "rule_name", None),
                    )
                )

            try:
                if decision.decision_type != DecisionType.EXECUTE:
                    if self._event_bus:
                        self._event_bus.publish(
                            AutomationExecutedEvent(
                                intent=decision.decision_type.value,
                                action=decision.decision_type.value,
                                success=False,
                                execution_status=decision.message,
                            )
                        )
                    self._speak_response(decision.message)
                    return VoicePipelineResult(
                        intent=decision.decision_type.value,
                        message=decision.message,
                        success=False,
                        transcript=text,
                    )

                executable_intent = VoiceIntent(
                    intent=decision.intent,
                    text=text,
                    target=decision.target,
                    query=decision.query,
                    params=decision.params,
                )

                if not self._action_engine_allows(executable_intent):
                    msg = "Action blocked by ActionEngine cooldown/pause."
                    self._speak_response(msg)
                    return VoicePipelineResult(
                        intent=executable_intent.intent.value,
                        message=msg,
                        success=False,
                        transcript=text,
                    )

                automation_result = self._automation_dispatcher.dispatch(executable_intent)
                logger.info(
                    "ACTION: Voice action executed: %s (success: %s, message: '%s')",
                    automation_result.intent.value,
                    automation_result.success,
                    automation_result.message,
                )
                spoken_msg = self._format_spoken_response(executable_intent, automation_result.success, automation_result.message)
                if self._event_bus:
                    self._event_bus.publish(
                        AutomationExecutedEvent(
                            intent=automation_result.intent.value,
                            action=automation_result.intent.value,
                            success=automation_result.success,
                            execution_status=spoken_msg,
                        )
                    )
                self._speak_response(spoken_msg)
                return VoicePipelineResult(
                    intent=automation_result.intent.value,
                    message=spoken_msg,
                    success=automation_result.success,
                    transcript=text,
                )
            except Exception as exc:
                logger.exception("Uncaught exception in VoiceCommandPipeline execution: %s", exc)
                fallback_msg = "Sir, I couldn't complete that command."
                self._speak_response(fallback_msg)
                return VoicePipelineResult(
                    intent="ERROR",
                    message=fallback_msg,
                    success=False,
                    transcript=text,
                )

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

    def _speak_response(self, text: str) -> None:
        """Synthesize and speak assistant response via attached SpeechOutputManager."""
        if not text:
            return
        som = getattr(self, "_speech_output_manager", None)
        if som is not None and hasattr(som, "speak"):
            try:
                som.speak(text)
            except Exception:
                logger.exception("Failed to speak assistant response via SpeechOutputManager.")

    @staticmethod
    def _format_spoken_response(intent: VoiceIntent, success: bool, raw_message: str) -> str:
        """Format natural human speech responses for completed actions."""
        if raw_message:
            return raw_message

        from backend.automation.app_resolver import app_resolver
        canonical = app_resolver.get_canonical_name(intent.target or "") if intent.target else None
        display_target = canonical or (intent.target or "").strip().title() or "Application"

        if not success:
            return f"Sir, I couldn't find {display_target} on this computer."

        intent_type = intent.intent

        if intent_type in (VoiceIntentType.OPEN_APPLICATION, VoiceIntentType.OPEN_CHROME, VoiceIntentType.OPEN_NOTEPAD):
            return f"{display_target} opened."

        if intent_type in (VoiceIntentType.CLOSE_APPLICATION, VoiceIntentType.CLOSE_WINDOW):
            return f"{display_target} closed."

        if intent_type == VoiceIntentType.EXIT_APPLICATION:
            return "Closing IRIS, sir."

        return raw_message

        if intent_type == VoiceIntentType.BROWSER_SEARCH:
            return "Done, sir."

        return raw_message
