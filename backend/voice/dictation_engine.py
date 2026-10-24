"""Faster-Whisper Dictation Engine for Gaze-Dictation ("Look & Type")."""

from __future__ import annotations

import os
from typing import Any
import numpy as np

from backend.core.config.settings import settings, APP_DATA_DIR
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class WhisperDictationEngine:
    """
    Faster-Whisper Dictation Engine for real-time speech-to-text dictation.
    Uses 'tiny.en' CPU int8 model for fast transcription.
    Provides graceful mock/fallback mode if faster-whisper or model is unavailable.
    """

    def __init__(self, model_size: str = "tiny.en", device: str = "cpu", compute_type: str = "int8") -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.ready = False
        self.mock_mode = False
        self._model: Any | None = None

        self._initialize_model()

    def _initialize_model(self) -> None:
        try:
            from faster_whisper import WhisperModel
            download_dir = str(APP_DATA_DIR / "models" / "whisper")
            os.makedirs(download_dir, exist_ok=True)
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                download_root=download_dir,
                cpu_threads=4,
            )
            self.ready = True
            logger.info("[DICTATION] Faster-Whisper model ('%s') initialized successfully.", self.model_size)
        except Exception as err:
            logger.warning("[DICTATION] Faster-Whisper initialization skipped/failed (%s). Fallback mode enabled.", err)
            self.mock_mode = True

    def transcribe_audio_buffer(self, pcm_data: bytes | np.ndarray) -> str:
        """
        Transcribe 16kHz float32 or int16 PCM audio buffer into text.
        """
        if not pcm_data or (isinstance(pcm_data, np.ndarray) and pcm_data.size == 0):
            return ""

        if not self.ready or self.mock_mode or self._model is None:
            return ""

        try:
            # Convert bytes to numpy float32 array if needed
            if isinstance(pcm_data, bytes):
                audio_np = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                audio_np = pcm_data.astype(np.float32)

            segments, _ = self._model.transcribe(
                audio_np,
                beam_size=1,
                language="en",
                vad_filter=True,
                without_timestamps=True,
            )
            text_parts = [segment.text.strip() for segment in segments if segment.text]
            full_text = " ".join(text_parts).strip()
            return full_text
        except Exception as err:
            logger.exception("[DICTATION] Error during audio transcription: %s", err)
            return ""
