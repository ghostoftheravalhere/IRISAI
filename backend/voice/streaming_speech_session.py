"""Real-time Streaming Speech Recognition Session."""

from __future__ import annotations

from threading import RLock
from typing import Any

from backend.core.events.bus import EventBus
from backend.utils.logger import get_logger
from backend.voice.streaming_events import PartialTranscriptEvent
from backend.voice.streaming_models import StreamingTranscript

logger = get_logger(__name__)


class StreamingSpeechSession:
    """Manages continuous audio chunking and emits streaming transcript frames."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus
        self._buffer: list[str] = []
        self._is_active = False
        self._lock = RLock()

    def start_session(self) -> None:
        with self._lock:
            self._buffer.clear()
            self._is_active = True
            logger.info("Started StreamingSpeechSession.")

    def process_chunk(self, chunk_text: str, is_final: bool = False) -> StreamingTranscript:
        """Process incoming audio text chunk and return StreamingTranscript."""
        with self._lock:
            if chunk_text:
                self._buffer.append(chunk_text)

            full_text = " ".join(self._buffer).strip()
            frame = StreamingTranscript(text=full_text, is_final=is_final)

            if self._event_bus:
                self._event_bus.publish(PartialTranscriptEvent(text=full_text, is_final=is_final))

            return frame

    def end_session(self) -> str:
        with self._lock:
            final_text = " ".join(self._buffer).strip()
            self._is_active = False
            self._buffer.clear()
            logger.info("Ended StreamingSpeechSession: '%s'", final_text)
            return final_text
