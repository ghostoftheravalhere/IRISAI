"""Real-Time Person Recognition Service connecting camera frames to IdentityManager & WorldModel.

Executes non-blocking background face recognition, updates WorldModel, and enforces
conversational debouncing / cooldown to prevent repetitive greeting spam.
"""

from __future__ import annotations

import concurrent.futures
from threading import RLock
import time
from typing import Any, Callable

from backend.brain.world_model import world_model
from backend.perception.camera.face_embedding_provider import MediaPipeFaceEmbeddingProvider
from backend.perception.identity_manager import (
    EnrollmentStatus,
    IdentityManager,
    PersonRecord,
    identity_manager,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class RealtimePersonRecognitionService:
    """Non-blocking background face recognition service managing real-time identity state."""

    def __init__(
        self,
        id_manager: IdentityManager | None = None,
        embedding_provider: Any | None = None,
        cooldown_seconds: float = 10.0,
        voice_prompt_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._id_manager = id_manager or identity_manager
        self._embedding_provider = embedding_provider or MediaPipeFaceEmbeddingProvider()
        self._cooldown_seconds = cooldown_seconds
        self._voice_callback = voice_prompt_callback

        self._lock = RLock()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._is_busy = False

        self._last_announced_name: str | None = None
        self._last_announced_time: float = 0.0
        self._last_face_seen_time: float = 0.0

    def process_landmarks_async(self, landmarks_or_frame: Any) -> None:
        """Enqueue landmark geometry embedding & identity recognition task asynchronously."""
        if landmarks_or_frame is None:
            with self._lock:
                # If no face has been seen for > 3 seconds, reset active session announcement state
                if time.time() - self._last_face_seen_time > 3.0:
                    self._last_announced_name = None
            return

        with self._lock:
            self._last_face_seen_time = time.time()
            if self._is_busy:
                return  # Drop frame if previous recognition task is still executing in background
            self._is_busy = True

        try:
            self._executor.submit(self._run_recognition_task, landmarks_or_frame)
        except Exception as exc:
            logger.error("Failed to submit recognition task: %s", exc)
            with self._lock:
                self._is_busy = False

    def _run_recognition_task(self, landmarks_or_frame: Any) -> None:
        """Background thread worker for face embedding & identity matching."""
        try:
            embedding = self._embedding_provider.compute_embedding(landmarks_or_frame)
            matched_rec = self._id_manager.process_face_embedding(embedding)
            self._evaluate_announcement_cooldown(matched_rec)
        except Exception as exc:
            logger.exception("Error in background face recognition task: %s", exc)
        finally:
            with self._lock:
                self._is_busy = False

    def _evaluate_announcement_cooldown(self, rec: PersonRecord) -> None:
        """Evaluate cooldown/debounce rules before triggering voice prompts."""
        now = time.time()
        with self._lock:
            time_since_last = now - self._last_announced_time

            # Enrolled KNOWN Person (e.g. "Rahul")
            if rec.status == EnrollmentStatus.KNOWN.value and rec.name:
                if rec.name != self._last_announced_name or time_since_last > self._cooldown_seconds:
                    self._last_announced_name = rec.name
                    self._last_announced_time = now
                    prompt = f"That's {rec.name}."
                    logger.info("Recognition event: %s", prompt)
                    if self._voice_callback:
                        self._voice_callback(prompt)

            # UNKNOWN Person
            elif rec.status in (EnrollmentStatus.UNKNOWN.value, EnrollmentStatus.PENDING_IDENTIFICATION.value):
                if self._last_announced_name != "UNKNOWN" or time_since_last > self._cooldown_seconds:
                    self._last_announced_name = "UNKNOWN"
                    self._last_announced_time = now
                    prompt = "I don't recognize this person. Who is this?"
                    logger.info("Recognition event: %s", prompt)
                    if self._voice_callback:
                        self._voice_callback(prompt)

    def set_voice_callback(self, callback: Callable[[str], None]) -> None:
        """Set voice prompt callback."""
        with self._lock:
            self._voice_callback = callback

    def shutdown(self) -> None:
        """Shutdown background thread executor."""
        self._executor.shutdown(wait=False)


person_recognition_service = RealtimePersonRecognitionService()
