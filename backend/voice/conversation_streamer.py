"""Conversation Streamer Telemetry Coordinator."""

from __future__ import annotations

from threading import RLock

from backend.core.events.bus import EventBus
from backend.utils.logger import get_logger
from backend.voice.incremental_reasoner import IncrementalReasoner
from backend.voice.streaming_speech_session import StreamingSpeechSession

logger = get_logger(__name__)


class ConversationStreamer:
    """Coordinates live audio streaming, partial intent updates, and HUD telemetry."""

    def __init__(
        self,
        event_bus: EventBus | None = None,
        reasoner: IncrementalReasoner | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._session = StreamingSpeechSession(event_bus=event_bus)
        self._reasoner = reasoner or IncrementalReasoner()
        self._lock = RLock()

    @property
    def session(self) -> StreamingSpeechSession:
        return self._session

    def process_live_chunk(self, chunk_text: str, is_final: bool = False) -> dict:
        """Process a live text/audio chunk and return partial telemetry."""
        with self._lock:
            frame = self._session.process_chunk(chunk_text, is_final=is_final)
            partial_intent = self._reasoner.predict_partial(frame.text)

            return {
                "text": frame.text,
                "is_final": frame.is_final,
                "predicted_intent": partial_intent.intent_name,
                "target": partial_intent.target,
                "query": partial_intent.query,
                "is_stable": partial_intent.is_stable,
            }
