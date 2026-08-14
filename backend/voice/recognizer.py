"""Continuous and push-to-talk microphone recognition using Faster-Whisper."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from threading import Event, RLock, Thread
from typing import Any

from backend.core.events.bus import EventBus
from backend.utils.logger import get_logger
from backend.voice.preprocessor import AdaptiveGainControlFilter, AudioPreprocessor, PeakLimiterFilter
from backend.voice.telemetry import AudioCapturedEvent, TranscriptionCompletedEvent

logger = get_logger(__name__)

TranscriptHandler = Callable[[str], tuple[str, str]]


class ListenMode(str, Enum):
    """Microphone listening modes."""

    CONTINUOUS = "continuous"
    PUSH_TO_TALK = "push_to_talk"


# Keep Whisper unbiased for short clips; command-heavy prompts can turn silence
# or low-noise audio into actionable command hallucinations.
_COMMAND_INITIAL_PROMPT: str | None = None


@dataclass(frozen=True)
class VoiceRecognitionConfig:
    """Voice recognition runtime configuration."""

    model_size: str = "base"
    sample_rate: int = 16000
    language: str = "en"
    device: str = "cpu"
    compute_type: str = "int8"
    block_duration_seconds: float = 0.25
    silence_threshold: float = 0.010
    silence_duration_seconds: float = 0.55
    min_utterance_seconds: float = 0.35
    max_utterance_seconds: float = 4.0
    trailing_silence_blocks: int = 1
    peak_norm_target: float = 0.85
    no_speech_threshold: float = 0.55
    listen_mode: ListenMode = ListenMode.CONTINUOUS
    enable_agc: bool = True
    target_rms: float = 0.04
    max_agc_gain: float = 40.0
    preprocessor: AudioPreprocessor | None = None
    event_bus: EventBus | None = None


@dataclass(frozen=True)
class VoiceRecognitionState:
    """Current voice recognition status exposed to the API."""

    microphoneStatus: str
    listening: bool
    listenMode: str
    pushToTalkActive: bool
    latestTranscript: str | None
    detectedIntent: str | None
    executionStatus: str
    error: str | None


class VoiceRecognitionService:
    """Capture microphone audio and expose the latest recognized command text."""

    def __init__(
        self,
        config: VoiceRecognitionConfig | None = None,
        on_transcript: TranscriptHandler | None = None,
    ) -> None:
        self._config = config or VoiceRecognitionConfig()
        self._on_transcript = on_transcript
        self._event_bus = self._config.event_bus
        self._preprocessor = self._config.preprocessor or AudioPreprocessor(
            filters=[
                AdaptiveGainControlFilter(
                    target_rms=self._config.target_rms,
                    max_gain=self._config.max_agc_gain,
                    enabled=self._config.enable_agc,
                ),
                PeakLimiterFilter(),
            ],
            enabled=True,
        )
        self._model: Any | None = None
        self._thread: Thread | None = None
        self._stop_event = Event()
        self._ptt_active = Event()
        self._lock = RLock()
        self._listening = False
        self._listen_mode = self._config.listen_mode
        self._microphone_status = "Off"
        self._latest_transcript: str | None = None
        self._detected_intent: str | None = None
        self._execution_status = "Idle"
        self._error: str | None = None
        self._validate_config(self._config)

    def start(self, mode: ListenMode | str | None = None) -> VoiceRecognitionState:
        """Start listening in a background thread."""
        with self._lock:
            if self._listening:
                return self.get_state()

            if mode is not None:
                self._listen_mode = self._coerce_mode(mode)

            self._stop_event.clear()
            self._ptt_active.clear()
            self._error = None
            self._execution_status = "Starting"
            self._microphone_status = "Starting"
            self._thread = Thread(target=self._run_loop, name="voice-recognition", daemon=True)
            self._thread.start()
            return self.get_state()

    def stop(self) -> VoiceRecognitionState:
        """Stop listening and wait briefly for the background thread to exit."""
        thread: Thread | None
        with self._lock:
            self._stop_event.set()
            self._ptt_active.clear()
            thread = self._thread

        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

        with self._lock:
            self._listening = False
            self._microphone_status = "Off"
            self._execution_status = "Stopped"
            self._thread = None
            return self.get_state()

    def set_mode(self, mode: ListenMode | str) -> VoiceRecognitionState:
        """Switch between continuous and push-to-talk listening."""
        with self._lock:
            self._listen_mode = self._coerce_mode(mode)
            if self._listen_mode != ListenMode.PUSH_TO_TALK:
                self._ptt_active.clear()
            if self._listening and self._error is None:
                self._execution_status = self._status_for_mode()
            return self.get_state()

    def push_to_talk_start(self) -> VoiceRecognitionState:
        """Begin capturing audio while push-to-talk mode is active."""
        with self._lock:
            logger.info("TRACE [1/11]: push_to_talk_start() called. listening=%s, mode=%s", self._listening, self._listen_mode)
            if self._listen_mode != ListenMode.PUSH_TO_TALK:
                self._error = "Push-to-talk is only available in push_to_talk mode."
                logger.info("TRACE STOPPED AT [1/11]: Push-to-talk rejected (not in push_to_talk mode).")
                return self.get_state()
            if not self._listening:
                self._error = "Voice recognition is not listening. Call start first."
                logger.info("TRACE STOPPED AT [1/11]: Push-to-talk rejected (not listening).")
                return self.get_state()

            self._error = None
            self._ptt_active.set()
            self._execution_status = "Push-to-talk active"
            self._microphone_status = "On"
            return self.get_state()

    def push_to_talk_stop(self) -> VoiceRecognitionState:
        """Stop capturing audio in push-to-talk mode and flush any buffered speech."""
        with self._lock:
            logger.info("TRACE [PTT STOP]: push_to_talk_stop() called. Clearing PTT active flag.")
            self._ptt_active.clear()
            if self._listening and self._listen_mode == ListenMode.PUSH_TO_TALK:
                self._execution_status = "Waiting for push-to-talk"
            return self.get_state()

    def get_state(self) -> VoiceRecognitionState:
        """Return the latest recognition state."""
        with self._lock:
            return VoiceRecognitionState(
                microphoneStatus=self._microphone_status,
                listening=self._listening,
                listenMode=self._listen_mode.value,
                pushToTalkActive=self._ptt_active.is_set(),
                latestTranscript=self._latest_transcript,
                detectedIntent=self._detected_intent,
                executionStatus=self._execution_status,
                error=self._error,
            )

    def _run_loop(self) -> None:
        """Read microphone audio until stopped, transcribing utterances after silence."""
        try:
            sd, np = self._load_audio_dependencies()
            self._load_model()
            block_size = int(self._config.sample_rate * self._config.block_duration_seconds)
            silence_blocks_required = max(
                1,
                int(self._config.silence_duration_seconds / self._config.block_duration_seconds),
            )
            min_blocks_required = max(
                1,
                int(self._config.min_utterance_seconds / self._config.block_duration_seconds),
            )
            max_blocks = max(
                min_blocks_required,
                int(self._config.max_utterance_seconds / self._config.block_duration_seconds),
            )
            trailing_blocks = max(0, int(self._config.trailing_silence_blocks))

            with sd.InputStream(
                samplerate=self._config.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=block_size,
            ) as stream:
                with self._lock:
                    self._listening = True
                    self._microphone_status = "On"
                    self._execution_status = self._status_for_mode()

                speech_blocks: list[Any] = []
                silent_blocks = 0
                trailing_buffer: list[Any] = []

                while not self._stop_event.is_set():
                    with self._lock:
                        is_ptt_mode = (self._listen_mode == ListenMode.PUSH_TO_TALK)

                    if not self._should_capture():
                        if speech_blocks:
                            logger.info("TRACE [2/11]: _run_loop() receives audio! PTT released and audio buffer flushed.")
                            logger.info("TRACE [3/11]: Number of captured blocks = %d", len(speech_blocks))
                            audio = np.concatenate(speech_blocks)
                            self._handle_audio(audio)
                            speech_blocks = []
                            silent_blocks = 0
                            trailing_buffer = []
                        self._stop_event.wait(self._config.block_duration_seconds)
                        continue

                    block, overflowed = stream.read(block_size)
                    if overflowed:
                        logger.warning("Microphone input overflow while listening.")

                    mono_block = np.asarray(block, dtype=np.float32).reshape(-1)

                    if is_ptt_mode:
                        # Push-to-Talk mode: bypass RMS gating and accumulate every block while PTT is active.
                        speech_blocks.append(mono_block.copy())
                        continue

                    # Continuous mode: RMS silence gating and endpointing logic.
                    rms = float(np.sqrt(np.mean(np.square(mono_block)))) if mono_block.size else 0.0

                    if rms >= self._config.silence_threshold:
                        if trailing_buffer and not speech_blocks:
                            # Keep a little pre-roll so onsets are not clipped.
                            speech_blocks.extend(trailing_buffer)
                        trailing_buffer = []
                        speech_blocks.append(mono_block.copy())
                        silent_blocks = 0
                        if len(speech_blocks) >= max_blocks:
                            audio = np.concatenate(speech_blocks)
                            self._handle_audio(audio)
                            speech_blocks = []
                            silent_blocks = 0
                        continue

                    if speech_blocks:
                        # Retain a short trailing pad so word endings survive endpointing.
                        speech_blocks.append(mono_block.copy())
                        silent_blocks += 1
                    else:
                        trailing_buffer.append(mono_block.copy())
                        if len(trailing_buffer) > trailing_blocks:
                            trailing_buffer.pop(0)

                    if speech_blocks and silent_blocks >= silence_blocks_required:
                        if len(speech_blocks) >= min_blocks_required:
                            audio = np.concatenate(speech_blocks)
                            self._handle_audio(audio)
                        else:
                            with self._lock:
                                if self._latest_transcript is None:
                                    self._execution_status = "Empty speech"
                        speech_blocks = []
                        silent_blocks = 0
                        trailing_buffer = []
        except Exception as exc:
            logger.exception("Voice recognition failed.")
            message = str(exc)
            with self._lock:
                if "sounddevice" in message.lower() or "portaudio" in message.lower():
                    self._error = "Microphone unavailable."
                elif "faster-whisper" in message.lower() or "whisper" in message.lower():
                    self._error = "Whisper failure."
                else:
                    self._error = message
                self._execution_status = "Error"
                self._microphone_status = "Error"
        finally:
            with self._lock:
                self._listening = False
                if self._execution_status != "Error":
                    self._microphone_status = "Off"
                self._ptt_active.clear()
                self._thread = None

    def _should_capture(self) -> bool:
        """Return whether the current mode should capture microphone audio."""
        with self._lock:
            mode = self._listen_mode
        if mode == ListenMode.CONTINUOUS:
            return True
        return self._ptt_active.is_set()

    def _status_for_mode(self) -> str:
        """Human-readable status for the active listen mode."""
        if self._listen_mode == ListenMode.PUSH_TO_TALK:
            return "Waiting for push-to-talk" if not self._ptt_active.is_set() else "Push-to-talk active"
        return "Listening"

    def _handle_audio(self, audio: Any) -> None:
        """Transcribe captured audio and dispatch the transcript callback."""
        raw_wav_file = "c:/Users/Meet Raval/IRISAI/live_debug_raw.wav"
        prep_wav_file = "c:/Users/Meet Raval/IRISAI/live_debug_prep.wav"
        try:
            import wave
            import numpy as np

            raw_samples = np.asarray(audio, dtype=np.float32).reshape(-1)
            raw_rms = float(np.sqrt(np.mean(np.square(raw_samples)))) if raw_samples.size else 0.0
            raw_peak = float(np.max(np.abs(raw_samples))) if raw_samples.size else 0.0
            duration = float(raw_samples.size / self._config.sample_rate) if self._config.sample_rate else 0.0

            # Save RAW WAV
            int_raw = (np.clip(raw_samples, -1.0, 1.0) * 32767.0).astype(np.int16)
            with wave.open(raw_wav_file, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self._config.sample_rate)
                wf.writeframes(int_raw.tobytes())

            prep_samples = self._preprocess_audio(raw_samples)
            int_prep = (np.clip(prep_samples, -1.0, 1.0) * 32767.0).astype(np.int16)
            with wave.open(prep_wav_file, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self._config.sample_rate)
                wf.writeframes(int_prep.tobytes())

            with self._lock:
                vad_active = (self._listen_mode == ListenMode.PUSH_TO_TALK)

            logger.info("=== LIVE UTTERANCE AUDIT LOG ===")
            logger.info("  Raw Microphone RMS   : %.6f", raw_rms)
            logger.info("  Raw Microphone Peak  : %.6f", raw_peak)
            logger.info("  Audio Duration       : %.3fs", duration)
            logger.info("  Saved RAW wav        : %s", raw_wav_file)
            logger.info("  Saved PREPROCESSED   : %s", prep_wav_file)
            logger.info("  Whisper Model Name   : %s", self._config.model_size)
            logger.info("  Whisper Parameters   : language=%s, beam_size=5, vad_filter=%s, initial_prompt='%s'",
                        self._config.language, vad_active, _COMMAND_INITIAL_PROMPT)
            if self._event_bus:
                self._event_bus.publish(
                    AudioCapturedEvent(
                        raw_rms=raw_rms,
                        raw_peak=raw_peak,
                        duration_seconds=duration,
                        is_ptt=vad_active,
                    )
                )
        except Exception:
            logger.exception("Voice debug audio metric logging failed.")

        try:
            import time
            t0 = time.time()
            transcript = self._transcribe(audio)
            latency_ms = (time.time() - t0) * 1000.0

            if self._event_bus:
                self._event_bus.publish(
                    TranscriptionCompletedEvent(
                        raw_transcript=transcript,
                        whisper_latency_ms=latency_ms,
                    )
                )
        except Exception:
            logger.exception("Whisper transcription failed.")
            with self._lock:
                self._error = "Whisper failure."
                self._execution_status = "Error"
            return

        if not transcript:
            logger.info("  Raw Transcript       : '<EMPTY>'")
            logger.info("  Normalized Transcript: '<EMPTY>'")
            logger.info("  Final Intent         : %s", VoiceRecognitionService._empty_intent() if self._latest_transcript is None else self._detected_intent)
            logger.info("================================")
            with self._lock:
                if self._latest_transcript is None:
                    self._detected_intent = VoiceRecognitionService._empty_intent()
                    self._execution_status = "Empty speech"
                self._error = None
            return

        detected_intent = "NO_INTENT"
        execution_status = "Transcript captured."
        if self._on_transcript is not None:
            try:
                detected_intent, execution_status = self._on_transcript(transcript)
            except Exception:
                logger.exception("Voice transcript handler failed.")
                execution_status = "Intent handling failed."

        logger.info("  Raw Transcript       : '%s'", transcript)
        logger.info("  Final Intent         : %s", detected_intent)
        logger.info("  Execution Status     : %s", execution_status)
        logger.info("================================")

        with self._lock:
            self._latest_transcript = transcript
            self._detected_intent = detected_intent
            self._execution_status = execution_status
            self._error = None

    def _transcribe(self, audio: Any) -> str:
        """Run Faster-Whisper transcription for one utterance."""
        import numpy as np

        model = self._load_model()
        prepared = self._preprocess_audio(np.asarray(audio, dtype=np.float32))
        with self._lock:
            use_vad_filter = (self._listen_mode == ListenMode.PUSH_TO_TALK)

        segments, _info = model.transcribe(
            prepared,
            language=self._config.language,
            task="transcribe",
            vad_filter=use_vad_filter,
            beam_size=5,
            best_of=5,
            temperature=0.0,
            condition_on_previous_text=False,
            initial_prompt=_COMMAND_INITIAL_PROMPT,
            no_speech_threshold=self._config.no_speech_threshold,
            compression_ratio_threshold=2.4,
            without_timestamps=True,
        )

        parts: list[str] = []
        logger.info("Whisper:")
        for segment in segments:
            text = (segment.text or "").strip()
            no_speech = float(getattr(segment, "no_speech_prob", 0.0) or 0.0)
            avg_logprob = float(getattr(segment, "avg_logprob", 0.0) or 0.0)
            logger.info("TRACE [8/11]: no_speech_prob = %.6f", no_speech)
            logger.info("TRACE [9/11]: avg_logprob = %.6f", avg_logprob)
            logger.info("- segment.text: %s", text)
            logger.info("- no_speech_prob: %.6f (threshold: %.6f)", no_speech, self._config.no_speech_threshold)
            logger.info("- avg_logprob: %.6f", avg_logprob)
            if not text:
                logger.info("  -> Dropped: empty segment text")
                continue
            if no_speech >= self._config.no_speech_threshold:
                logger.info("  -> Dropped by secondary no_speech_threshold (%.6f >= %.6f)", no_speech, self._config.no_speech_threshold)
                continue
            logger.info("  -> Kept segment text: %s", text)
            parts.append(text)
        result_text = " ".join(parts).strip()
        logger.info("TRACE [7/11]: Transcript returned by Whisper = '%s'", result_text)
        return result_text

    def _preprocess_audio(self, audio: Any) -> Any:
        """Preprocess audio via injected AudioPreprocessor pipeline."""
        import numpy as np

        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return samples

        return self._preprocessor.process(samples, self._config.sample_rate)

    def _load_model(self) -> Any:
        """Load Faster-Whisper lazily on first listening session."""
        with self._lock:
            if self._model is not None:
                return self._model

        try:
            from faster_whisper import WhisperModel
        except Exception as exc:
            raise RuntimeError("faster-whisper is not installed or could not be loaded") from exc

        try:
            model = WhisperModel(
                self._config.model_size,
                device=self._config.device,
                compute_type=self._config.compute_type,
            )
        except Exception as exc:
            raise RuntimeError("Whisper failure.") from exc

        with self._lock:
            self._model = model
            return self._model

    @staticmethod
    def _empty_intent() -> str:
        return "NO_INTENT"

    @staticmethod
    def _coerce_mode(mode: ListenMode | str) -> ListenMode:
        if isinstance(mode, ListenMode):
            return mode
        normalized = str(mode).strip().lower().replace("-", "_")
        try:
            return ListenMode(normalized)
        except ValueError as exc:
            raise ValueError("listen_mode must be 'continuous' or 'push_to_talk'.") from exc

    @staticmethod
    def _load_audio_dependencies() -> tuple[Any, Any]:
        """Import audio dependencies lazily to keep app startup light."""
        try:
            import numpy as np
            import sounddevice as sd
        except Exception as exc:
            raise RuntimeError("Microphone unavailable.") from exc

        return sd, np

    @staticmethod
    def _validate_config(config: VoiceRecognitionConfig) -> None:
        """Validate microphone and model settings."""
        if config.sample_rate <= 0:
            raise ValueError("sample_rate must be positive.")
        if config.block_duration_seconds <= 0.0:
            raise ValueError("block_duration_seconds must be positive.")
        if config.silence_threshold <= 0.0:
            raise ValueError("silence_threshold must be positive.")
        if config.silence_duration_seconds <= 0.0:
            raise ValueError("silence_duration_seconds must be positive.")
        if config.min_utterance_seconds <= 0.0:
            raise ValueError("min_utterance_seconds must be positive.")
        if config.max_utterance_seconds < config.min_utterance_seconds:
            raise ValueError("max_utterance_seconds must be >= min_utterance_seconds.")
        if config.trailing_silence_blocks < 0:
            raise ValueError("trailing_silence_blocks cannot be negative.")
        if not 0.0 < config.peak_norm_target <= 1.0:
            raise ValueError("peak_norm_target must be in (0.0, 1.0].")
        if not 0.0 <= config.no_speech_threshold <= 1.0:
            raise ValueError("no_speech_threshold must be in [0.0, 1.0].")
        if not isinstance(config.listen_mode, ListenMode):
            raise ValueError("listen_mode must be a ListenMode value.")
