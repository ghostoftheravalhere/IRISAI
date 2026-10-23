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
import os
import sys

def _register_cuda_dll_directories() -> None:
    """Ensure NVIDIA cuDNN and cuBLAS DLL directories are discoverable on Windows."""
    if sys.platform != "win32":
        return
    try:
        from pathlib import Path
        import shutil
        site_packages = Path(sys.prefix) / "Lib" / "site-packages"
        ct2_dir = site_packages / "ctranslate2"
        for sub in ("nvidia/cudnn/bin", "nvidia/cublas/bin"):
            dll_dir = site_packages / sub
            if dll_dir.exists():
                try:
                    os.add_dll_directory(str(dll_dir))
                except Exception:
                    pass
                cur_path = os.environ.get("PATH", "")
                if str(dll_dir) not in cur_path:
                    os.environ["PATH"] = str(dll_dir) + os.pathsep + cur_path
                if ct2_dir.exists():
                    for dll in dll_dir.glob("*.dll"):
                        target_file = ct2_dir / dll.name
                        if not target_file.exists():
                            try:
                                shutil.copy2(str(dll), str(target_file))
                            except Exception:
                                pass
    except Exception:
        pass


_register_cuda_dll_directories()

import ctranslate2
from backend.core.config.settings import settings
from backend.voice.command_engine import VoskCommandEngine
from backend.voice.action_engine import MultimodalActionDispatcher

logger = get_logger(__name__)

TranscriptHandler = Callable[[str], tuple[str, str]]


def get_whisper_device_and_compute() -> tuple[str, str]:
    """Detect CUDA support for faster-whisper / ctranslate2; return device and compute_type."""
    try:
        # Check if CUDA device is available and functional
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"


_DEFAULT_WHISPER_DEVICE, _DEFAULT_WHISPER_COMPUTE = get_whisper_device_and_compute()


def resolve_whisper_model_path(model_size_or_name: str = "small.en", explicit_path: str | None = None) -> str:
    """
    Resolves the Faster-Whisper model size string or local directory path for offline use.
    Resolution order:
    1. explicit_path if provided and exists
    2. settings.VOICE_MODEL_PATH if set and exists
    3. Bundled production resources: resources/models/whisper-small.en, resources/models/whisper-base.en, or resources/models/<model_size>
    4. Fallback to model_size_or_name string for Hugging Face cache / dev mode
    """
    if explicit_path and os.path.exists(explicit_path):
        return explicit_path

    if settings.VOICE_MODEL_PATH and os.path.exists(settings.VOICE_MODEL_PATH):
        return settings.VOICE_MODEL_PATH

    search_dirs: list[str] = []

    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        meipass = getattr(sys, "_MEIPASS", exe_dir)
        search_dirs.extend([
            os.path.join(meipass, "resources", "models"),
            os.path.join(exe_dir, "resources", "models"),
            os.path.join(exe_dir, "..", "resources", "models"),
        ])

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    search_dirs.append(os.path.join(repo_root, "resources", "models"))

    candidate_names = [
        f"whisper-{model_size_or_name}",
        f"whisper-{model_size_or_name.replace('.', '-')}",
        f"whisper-{model_size_or_name}-en",
        model_size_or_name,
    ]

    for sdir in search_dirs:
        for name in candidate_names:
            candidate_path = os.path.join(sdir, name)
            if os.path.isdir(candidate_path) and os.path.exists(os.path.join(candidate_path, "model.bin")):
                logger.info("Resolved offline bundled Whisper model at: %s", candidate_path)
                return candidate_path

    return model_size_or_name


class ListenMode(str, Enum):
    """Microphone listening modes."""

    CONTINUOUS = "continuous"
    PUSH_TO_TALK = "push_to_talk"


_COMMAND_INITIAL_PROMPT = (
    "Commands: find, search, open chrome, notepad, camera, double click, "
    "right click, scroll down, scroll up, close window, open PC, desktop, "
    "files, documents, okay, done."
)


@dataclass(frozen=True)
class VoiceRecognitionConfig:
    """Voice recognition runtime configuration."""

    model_size: str = "small.en"
    model_path: str | None = None
    sample_rate: int = 16000
    language: str = "en"
    device: str = _DEFAULT_WHISPER_DEVICE
    compute_type: str = _DEFAULT_WHISPER_COMPUTE
    cpu_threads: int = 4
    block_duration_seconds: float = 0.25
    silence_threshold: float = 0.0035
    silence_duration_seconds: float = 0.85
    min_utterance_seconds: float = 0.35
    max_utterance_seconds: float = 4.0
    trailing_silence_blocks: int = 3
    peak_norm_target: float = 0.85
    no_speech_threshold: float = 0.80
    logprob_threshold: float = -1.0
    listen_mode: ListenMode = ListenMode.CONTINUOUS
    enable_agc: bool = True
    target_rms: float = 0.04
    min_agc_gain: float = 0.5
    max_agc_gain: float = 8.0
    peak_limit: float = 0.95
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
    ready: bool = True


class VoiceRecognitionService:
    """Capture microphone audio and expose the latest recognized command text."""

    def __init__(
        self,
        config: VoiceRecognitionConfig | None = None,
        on_transcript: TranscriptHandler | None = None,
        on_speech_start: Callable[[], None] | None = None,
    ) -> None:
        self._config = config or VoiceRecognitionConfig()
        self._on_transcript = on_transcript
        self._on_speech_start = on_speech_start
        self._event_bus = self._config.event_bus
        self._preprocessor = self._config.preprocessor or AudioPreprocessor(
            filters=[
                AdaptiveGainControlFilter(
                    target_rms=self._config.target_rms,
                    min_gain=self._config.min_agc_gain,
                    max_gain=self._config.max_agc_gain,
                    peak_limit=self._config.peak_limit,
                    enabled=self._config.enable_agc,
                ),
                PeakLimiterFilter(threshold=self._config.peak_limit),
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
        self._tts_suppression_until: float = 0.0
        self._tts_active: bool = False
        self._is_busy: bool = False
        self._command_engine = VoskCommandEngine(sample_rate=self._config.sample_rate)
        self._action_dispatcher = MultimodalActionDispatcher()
        self._validate_config(self._config)

    def set_busy(self, busy: bool) -> None:
        """Lock or unlock voice capture during asynchronous command execution (e.g. document search)."""
        with self._lock:
            self._is_busy = busy
            if busy:
                logger.info("[VOICE] System marked BUSY: incoming microphone speech ignored during async execution.")
            else:
                logger.info("[VOICE] System marked IDLE: microphone capture active.")

    def is_busy(self) -> bool:
        """Return whether the voice system is currently busy executing an async command."""
        with self._lock:
            return self._is_busy

    def set_on_speech_start(self, callback: Callable[[], None] | None) -> None:
        """Attach a callback triggered on speech onset / VAD activation."""
        with self._lock:
            self._on_speech_start = callback

    def set_tts_active(self, active: bool, duration_sec: float = 0.0) -> None:
        """Mark TTS as active/inactive and set hardware audio suppression window."""
        import time
        with self._lock:
            self._tts_active = active
            if active:
                self._tts_suppression_until = time.time() + duration_sec + 0.8
                logger.info("[TTS] MICROPHONE SUPPRESSED (duration: %.2fs + 0.8s settle)", duration_sec)
            else:
                self._tts_suppression_until = max(self._tts_suppression_until, time.time() + 0.8)
                logger.info("[TTS] MICROPHONE RESUMING (0.8s settling window active)")

    def is_tts_active(self) -> bool:
        """Return whether TTS output is currently playing or in post-speech settling period."""
        import time
        with self._lock:
            if self._tts_active or (time.time() < self._tts_suppression_until):
                return True
            som = getattr(self, "_speech_output_manager", None)
            return bool(som and getattr(som, "is_speaking", False))

    def suppress_microphone_for_tts(self, duration_sec: float = 1.0) -> None:
        """Temporarily suppress microphone capture and clear audio buffers during/after TTS."""
        self.set_tts_active(True, duration_sec)

    def start(self, mode: ListenMode | str | None = None) -> VoiceRecognitionState:
        """Start listening in a background thread."""
        old_thread: Thread | None = None
        with self._lock:
            if mode is not None:
                self._listen_mode = self._coerce_mode(mode)

            # If already listening with an active thread, return state
            if self._listening and self._thread is not None and self._thread.is_alive():
                return self.get_state()

            # If an old worker thread is shutting down, signal and join it first
            if self._thread is not None and self._thread.is_alive():
                self._stop_event.set()
                old_thread = self._thread

        if old_thread is not None and old_thread.is_alive():
            old_thread.join(timeout=3.0)

        with self._lock:
            self._stop_event.clear()
            self._ptt_active.clear()
            self._error = None
            self._latest_transcript = None
            self._detected_intent = None
            self._execution_status = "Starting"
            self._microphone_status = "Starting"
            import os
            import threading
            logger.info(
                "[MIC] PID=%d THREAD=%d INSTANCE=%d STARTING — Listen mode: %s",
                os.getpid(),
                threading.get_ident(),
                id(self),
                self._listen_mode.value,
            )
            self._thread = Thread(target=self._run_loop, name="voice-recognition", daemon=True)
            self._thread.start()
            return self.get_state()

    def stop(self) -> VoiceRecognitionState:
        """Stop listening and wait briefly for the background thread to exit."""
        thread: Thread | None = None
        import os
        import threading
        with self._lock:
            self._stop_event.set()
            self._ptt_active.clear()
            thread = self._thread

        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)

        with self._lock:
            self._listening = False
            self._microphone_status = "Off"
            self._execution_status = "Stopped"
            self._thread = None
            self._stop_event.clear()
            logger.info("[MIC] PID=%d THREAD=%d INSTANCE=%d STOPPED — Voice recognition stopped.", os.getpid(), threading.get_ident(), id(self))
            return self.get_state()

    def shutdown(self) -> VoiceRecognitionState:
        """Shutdown VoiceRecognitionService cleanly and close microphone stream."""
        import os
        import threading
        logger.info("[MIC] PID=%d THREAD=%d INSTANCE=%d SHUTDOWN REQUESTED.", os.getpid(), threading.get_ident(), id(self))
        return self.stop()

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

        if self._on_speech_start is not None:
            try:
                self._on_speech_start()
            except Exception:
                pass

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
                ready=True,
            )

    def verify_device_available(self) -> bool:
        """Check if an audio input device is available on the system."""
        try:
            sd, _ = self._load_audio_dependencies()
            dev = sd.query_devices(kind="input")
            return bool(dev)
        except Exception:
            return False

    def _create_stream(
        self,
        sd: Any,
        target_device_idx: Any = None,
        actual_sr: int | None = 16000,
        actual_block_size: int = 4800,
    ) -> Any:
        """Create and start sounddevice input stream with multi-channel support to prevent phase cancellation."""
        channels = 1
        try:
            if target_device_idx is not None:
                dev_info = sd.query_devices(target_device_idx, kind="input")
            else:
                dev_info = sd.query_devices(kind="input")
            max_in = int(dev_info.get("max_input_channels", 1))
            if max_in >= 2:
                channels = 2
        except Exception:
            channels = 1

        kwargs: dict[str, Any] = {
            "device": target_device_idx,
            "channels": channels,
            "dtype": "float32",
            "blocksize": actual_block_size,
        }
        if actual_sr is not None:
            kwargs["samplerate"] = actual_sr
        stream = sd.InputStream(**kwargs)
        stream.start()
        return stream

    def open_audio_stream_with_retry(
        self,
        sd: Any,
        target_device_idx: Any = None,
        actual_sr: int | None = 16000,
        actual_block_size: int = 4800,
        max_retries: int = 3,
        delay_sec: float = 0.25,
    ) -> Any:
        """Open audio input stream with retry loop and backoff for driver warm-up."""
        import time
        last_err = None
        for attempt in range(1, max_retries + 1):
            try:
                stream = self._create_stream(sd, target_device_idx, actual_sr, actual_block_size)
                logger.info(f"[AUDIO] Microphone stream initialized successfully on attempt {attempt}.")
                return stream
            except Exception as err:
                last_err = err
                logger.warning(
                    f"[AUDIO] Microphone init attempt {attempt}/{max_retries} failed ({err}). Retrying in {delay_sec}s..."
                )
                time.sleep(delay_sec)
        raise RuntimeError(f"Failed to initialize audio input after {max_retries} attempts: {last_err}")

    def get_diagnostics(self) -> dict[str, Any]:
        """Return safe, detailed real-time hardware microphone diagnostic information."""
        import time
        dev_name = "Unknown Input Device"
        default_input_idx = None
        sample_rate = self._config.sample_rate
        channels = 1
        try:
            sd, _ = self._load_audio_dependencies()
            default_input_idx = sd.default.device[0]
            devices = sd.query_devices()
            if default_input_idx is not None and 0 <= default_input_idx < len(devices):
                dev_info = devices[default_input_idx]
                dev_name = dev_info.get("name", "Unknown Input Device")
                sample_rate = int(dev_info.get("default_samplerate", self._config.sample_rate))
                channels = int(dev_info.get("max_input_channels", 1))
        except Exception:
            pass

        with self._lock:
            thread_alive = self._thread is not None and self._thread.is_alive()
            return {
                "status": self._microphone_status,
                "listening": self._listening,
                "listen_mode": self._listen_mode.value,
                "device_name": dev_name,
                "device_index": default_input_idx,
                "sample_rate": sample_rate,
                "channels": channels,
                "stream_open": self._listening and thread_alive,
                "recognizer_running": thread_alive,
                "last_error": self._error,
                "tts_suppressed": time.time() < self._tts_suppression_until,
            }

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

            logger.info("[MIC] Initializing microphone")
            logger.info("[MIC] Enumerating devices")

            target_device_idx, dev_name, actual_sr = self._enumerate_and_select_device(sd)
            logger.info("[MIC] Default input device = %s (Index: %s)", dev_name, target_device_idx)
            logger.info("[MIC] Sample rate = %d Hz (Target: %d Hz)", actual_sr, self._config.sample_rate)
            logger.info("[MIC] Backend = sounddevice (PortAudio)")

            import time
            stream = None
            needs_resampling = (actual_sr != self._config.sample_rate)
            actual_block_size = int(actual_sr * self._config.block_duration_seconds) if needs_resampling else block_size

            # Pre-warm & settling delay (250ms) to allow OS/PortAudio hardware handles to stabilize
            time.sleep(0.25)

            # Step 1: Attempt primary selected device with retry
            try:
                stream = self.open_audio_stream_with_retry(
                    sd=sd,
                    target_device_idx=target_device_idx,
                    actual_sr=actual_sr,
                    actual_block_size=actual_block_size,
                    max_retries=3,
                    delay_sec=0.25,
                )
            except Exception as stream_err:
                logger.warning(
                    "[MIC] Primary stream opening failed on device #%s (%s): %s. Falling back to system default...",
                    target_device_idx,
                    dev_name,
                    stream_err,
                )
                # Step 2: Fallback to system default input (device=None) at 16000 Hz or native rate with retry
                try:
                    actual_sr = 16000
                    actual_block_size = block_size
                    needs_resampling = False
                    stream = self.open_audio_stream_with_retry(
                        sd=sd,
                        target_device_idx=None,
                        actual_sr=16000,
                        actual_block_size=block_size,
                        max_retries=3,
                        delay_sec=0.25,
                    )
                    target_device_idx = sd.default.device[0] if hasattr(sd, "default") and getattr(sd.default, "device", None) else None
                    dev_name = "Default System Input"
                except Exception as fallback_err:
                    logger.warning("[MIC] Fallback at 16kHz failed (%s). Attempting native default rate with retry...", fallback_err)
                    try:
                        stream = self.open_audio_stream_with_retry(
                            sd=sd,
                            target_device_idx=None,
                            actual_sr=None,
                            actual_block_size=block_size,
                            max_retries=3,
                            delay_sec=0.25,
                        )
                        dev_name = "Default System Input (Native Rate)"
                    except Exception as final_err:
                        logger.exception("[MIC] All microphone InputStream creation attempts failed! %s", final_err)
                        raise final_err

            logger.info(
                "[MIC] Microphone initialized successfully (Device: '%s' [#%s], SR: %d Hz, Resample: %s)",
                dev_name,
                target_device_idx,
                actual_sr,
                needs_resampling,
            )

            try:
                with self._lock:
                    self._listening = True
                    self._microphone_status = "On"
                    self._execution_status = self._status_for_mode()
                logger.info("MICROPHONE_READY: Microphone input stream open.")
                logger.info("LISTENING: Voice recognition active.")

                speech_blocks: list[Any] = []
                silent_blocks = 0
                trailing_buffer: list[Any] = []
                dropped_blocks_count = 0
                while not self._stop_event.is_set():
                    import time
                    now = time.time()
                    with self._lock:
                        is_ptt_mode = (self._listen_mode == ListenMode.PUSH_TO_TALK)
                        is_tts_suppressed = (
                            self._tts_active
                            or (now < self._tts_suppression_until)
                            or (self._speech_output_manager and getattr(self._speech_output_manager, "is_speaking", False))
                        )
                        is_busy_locked = self._is_busy

                    # ALWAYS read stream to drain OS hardware audio buffers continuously!
                    block, overflowed = stream.read(actual_block_size)
                    if overflowed:
                        logger.warning("Microphone input overflow while listening.")

                    if is_tts_suppressed or is_busy_locked:
                        dropped_blocks_count += 1
                        speech_blocks = []
                        silent_blocks = 0
                        trailing_buffer = []
                        continue
                    else:
                        dropped_blocks_count = 0

                    if not self._should_capture():
                        if is_ptt_mode and speech_blocks:
                            audio = np.concatenate(speech_blocks)
                            self._handle_audio(audio)
                        speech_blocks = []
                        silent_blocks = 0
                        trailing_buffer = []
                        self._stop_event.wait(self._config.block_duration_seconds)
                        continue

                    raw_mono = self.select_audio_channel(block)
                    if needs_resampling and raw_mono.size > 0:
                        # Resample captured hardware audio to target 16000 Hz using band-limited polyphase filter
                        import math
                        from scipy.signal import resample_poly

                        gcd = math.gcd(int(actual_sr), 16000)
                        up = 16000 // gcd
                        down = int(actual_sr) // gcd
                        mono_block = resample_poly(raw_mono, up, down).astype(np.float32)
                    else:
                        mono_block = raw_mono

                    if mono_block.size > 0:
                        cmd_action = self._command_engine.process_audio_chunk(mono_block)
                        if cmd_action:
                            self._action_dispatcher.dispatch(cmd_action)

                    if is_ptt_mode:
                        speech_blocks.append(mono_block.copy())
                        continue

                    # Continuous mode: RMS silence gating and endpointing logic.
                    rms = float(np.sqrt(np.mean(np.square(mono_block)))) if mono_block.size else 0.0

                    if rms >= self._config.silence_threshold:
                        if not speech_blocks and self._on_speech_start is not None:
                            try:
                                self._on_speech_start()
                            except Exception:
                                pass
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
                        with self._lock:
                            if self._execution_status != "Error" or "Microphone" not in (self._error or ""):
                                self._execution_status = self._status_for_mode()
                                if "Microphone" not in (self._error or ""):
                                    self._error = None
                        speech_blocks = []
                        silent_blocks = 0
                        trailing_buffer = []
            finally:
                if stream is not None:
                    try:
                        stream.stop()
                        stream.close()
                    except Exception:
                        pass
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

    def set_speech_output_manager(self, speech_output_manager: Any) -> None:
        """Attach SpeechOutputManager to mute capture during TTS output."""
        with self._lock:
            self._speech_output_manager = speech_output_manager

    @staticmethod
    def _enumerate_and_select_device(sd: Any) -> tuple[int | None, str, int]:
        """Enumerate all available audio input devices and return default index, name, and native sample rate."""
        default_idx = None
        dev_name = "Default Input Device"
        sample_rate = 16000
        try:
            default_idx = sd.default.device[0]
            devices = sd.query_devices()
            logger.info("[MIC] Total audio devices found: %d", len(devices))
            for idx, dev in enumerate(devices):
                max_in = dev.get("max_input_channels", 0)
                if max_in > 0:
                    name = dev.get("name", f"Device {idx}")
                    sr = int(dev.get("default_samplerate", 16000))
                    logger.info("[MIC] Input Device #%d: '%s' | Channels: %d | Default SR: %d", idx, name, max_in, sr)

            if default_idx is not None and 0 <= default_idx < len(devices):
                info = devices[default_idx]
                if info.get("max_input_channels", 0) > 0:
                    dev_name = info.get("name", "Default Input Device")
                    sample_rate = int(info.get("default_samplerate", 16000))
                    return default_idx, dev_name, sample_rate

            for idx, dev in enumerate(devices):
                if dev.get("max_input_channels", 0) > 0:
                    dev_name = dev.get("name", f"Device {idx}")
                    sample_rate = int(dev.get("default_samplerate", 16000))
                    return idx, dev_name, sample_rate
        except Exception as exc:
            logger.warning("[MIC] Failed during device enumeration: %s", exc)

        return default_idx, dev_name, sample_rate

    @staticmethod
    def _select_input_device(sd: Any) -> tuple[int | None, int]:
        """Identify default or best valid system input device and sample rate."""
        idx, _, sr = VoiceRecognitionService._enumerate_and_select_device(sd)
        return idx, sr

    def _should_capture(self) -> bool:
        """Return whether the current mode should capture microphone audio."""
        import time
        now = time.time()
        with self._lock:
            if self._is_busy:
                return False
            if now < self._tts_suppression_until:
                return False
            mode = self._listen_mode
            som = getattr(self, "_speech_output_manager", None)
            if som is not None and getattr(som, "is_speaking", False):
                return False
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
        import os
        import threading
        if self.is_tts_active() or self.is_busy():
            logger.info(
                "[STT FIREWALL] ABORTING AUDIO PROCESSING — System is TTS suppressed or busy! (PID=%d THREAD=%d)",
                os.getpid(),
                threading.get_ident(),
            )
            return

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

            logger.info("AUDIO_CAPTURE: Audio utterance captured (duration: %.2fs, peak: %.4f)", duration, raw_peak)
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
            logger.info("TRANSCRIPTION: Raw transcript: '%s' (latency: %.1fms)", transcript, latency_ms)

            # HARD SAFETY GATE 1: Discard transcript if TTS is currently active or in settling window, or if system is busy
            if self.is_tts_active() or self.is_busy():
                import os
                import threading
                logger.warning(
                    "[FALSE TRANSCRIPT CANDIDATE REJECTED] TEXT='%s' TTS_ACTIVE=%s BUSY=%s STATE='%s' PID=%d THREAD=%d",
                    transcript,
                    self.is_tts_active(),
                    self.is_busy(),
                    self._execution_status,
                    os.getpid(),
                    threading.get_ident(),
                )
                with self._lock:
                    self._latest_transcript = None
                    self._execution_status = self._status_for_mode()
                return

            # HARD SAFETY GATE 2: Discard transcript if it matches IRIS assistant response text
            if self._is_iris_response_text(transcript):
                logger.warning("[STT FIREWALL] DISCARD TRANSCRIPT — Speech matches IRIS assistant response: '%s'", transcript)
                with self._lock:
                    self._latest_transcript = None
                    self._execution_status = self._status_for_mode()
                return

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

        if transcript:
            cmd_match = self._command_engine.process_text_command(transcript)
            if cmd_match:
                self._action_dispatcher.dispatch(cmd_match)
            elif self._action_dispatcher.dictation_active or self._action_dispatcher._single_type_pending:
                self._action_dispatcher.type_text(transcript)
                self._action_dispatcher._single_type_pending = False

        detected_intent = "NO_INTENT"
        execution_status = "Transcript captured."
        try:
            if self._on_transcript is not None:
                try:
                    detected_intent, execution_status = self._on_transcript(transcript)
                except Exception as exc:
                    logger.exception("Voice transcript handler failed: %s", exc)
                    execution_status = "Intent handling failed."
        finally:
            logger.info("  Raw Transcript       : '%s'", transcript)
            logger.info("  Final Intent         : %s", detected_intent)
            logger.info("  Execution Status     : %s", execution_status)
            logger.info("================================")

            with self._lock:
                self._latest_transcript = transcript
                self._detected_intent = detected_intent
                self._execution_status = self._status_for_mode()
                self._error = None

    def _transcribe(self, audio: Any) -> str:
        """Run Faster-Whisper transcription for one utterance."""
        import os
        import threading
        if self.is_tts_active():
            logger.info(
                "[STT FIREWALL] ABORTING WHISPER TRANSCRIBE — TTS is active or suppressed! (PID=%d THREAD=%d)",
                os.getpid(),
                threading.get_ident(),
            )
            return ""

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
            temperature=[0.0, 0.2],
            condition_on_previous_text=False,
            initial_prompt=_COMMAND_INITIAL_PROMPT,
            no_speech_threshold=self._config.no_speech_threshold,
            compression_ratio_threshold=2.4,
            without_timestamps=True,
        )

        parts: list[str] = []
        logger.info("Whisper:")
        for segment in segments:
            no_speech = float(getattr(segment, "no_speech_prob", 0.0) or 0.0)
            avg_logprob = float(getattr(segment, "avg_logprob", 0.0) or 0.0)
            logger.info("TRACE [8/11]: no_speech_prob = %.6f", no_speech)
            logger.info("TRACE [9/11]: avg_logprob = %.6f", avg_logprob)
            if not self.is_segment_valid(segment):
                continue
            text = (segment.text or "").strip()
            parts.append(text)
        result_text = " ".join(parts).strip()
        logger.info("TRACE [7/11]: Transcript returned by Whisper = '%s'", result_text)
        return result_text

    def is_segment_valid(self, segment: Any) -> bool:
        """Evaluate whether a Whisper segment is valid speech or noise/hallucination."""
        text = (getattr(segment, "text", "") or "").strip()
        if not text:
            logger.info("  -> Dropped: empty segment text")
            return False
        if not any(c.isalnum() for c in text):
            logger.info("  -> Dropped: non-alphanumeric/punctuation-only segment text")
            return False

        no_speech = float(getattr(segment, "no_speech_prob", 0.0) or 0.0)
        avg_logprob = float(getattr(segment, "avg_logprob", 0.0) or 0.0)

        no_speech_thresh = getattr(self._config, "no_speech_threshold", 0.80)
        logprob_thresh = getattr(self._config, "logprob_threshold", -1.0)

        logger.info("- segment.text: %s", text)
        logger.info("- no_speech_prob: %.6f (threshold: %.2f)", no_speech, no_speech_thresh)
        logger.info("- avg_logprob: %.6f (threshold: %.2f)", avg_logprob, logprob_thresh)

        # Combined filtering condition: reject only if BOTH no_speech_prob is elevated AND avg_logprob is low
        if no_speech >= no_speech_thresh and avg_logprob < logprob_thresh:
            logger.info(
                "  -> Dropped: low-confidence segment (no_speech_prob=%.4f >= %.2f and avg_logprob=%.4f < %.2f)",
                no_speech,
                no_speech_thresh,
                avg_logprob,
                logprob_thresh,
            )
            return False

        logger.info("  -> Kept segment text: %s", text)
        return True

    @staticmethod
    def select_audio_channel(block: Any) -> np.ndarray:
        """Select the louder microphone channel when stereo audio is provided, avoiding phase cancellation."""
        import numpy as np

        block_arr = np.asarray(block, dtype=np.float32)
        if block_arr.ndim == 2 and block_arr.shape[1] >= 2:
            ch0 = block_arr[:, 0]
            ch1 = block_arr[:, 1]
            rms0 = float(np.sqrt(np.mean(np.square(ch0)))) if ch0.size else 0.0
            rms1 = float(np.sqrt(np.mean(np.square(ch1)))) if ch1.size else 0.0
            return ch1 if rms1 > rms0 else ch0
        elif block_arr.ndim == 2:
            return block_arr[:, 0]
        else:
            return block_arr.reshape(-1)

    def _preprocess_audio(self, audio: Any) -> Any:
        """Preprocess audio via injected AudioPreprocessor pipeline with conditional peak protection."""
        import numpy as np

        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return samples

        if not np.all(np.isfinite(samples)):
            safe_limit = getattr(self._config, "peak_limit", 0.95)
            samples = np.nan_to_num(
                samples,
                nan=0.0,
                posinf=safe_limit,
                neginf=-safe_limit,
            ).astype(np.float32)

        processed = np.asarray(
            self._preprocessor.process(samples, self._config.sample_rate),
            dtype=np.float32,
        ).reshape(-1)
        if processed.size == 0:
            return processed

        # Conditional peak protection: preserve the gain selected by AGC,
        # only attenuate if peak exceeds safe limit (e.g. 0.95), preventing clipping/distortion.
        safe_peak_limit = getattr(self._config, "peak_limit", 0.95)
        peak = float(np.max(np.abs(processed)))
        if peak > safe_peak_limit and peak > 1e-6:
            processed = processed * (safe_peak_limit / peak)

        return np.ascontiguousarray(processed, dtype=np.float32)

    def _load_model(self) -> Any:
        """Load Faster-Whisper lazily on first listening session."""
        with self._lock:
            if self._model is not None:
                return self._model

        try:
            from faster_whisper import WhisperModel
        except Exception as exc:
            raise RuntimeError("faster-whisper is not installed or could not be loaded") from exc

        target_model_path = resolve_whisper_model_path(
            model_size_or_name=self._config.model_size,
            explicit_path=self._config.model_path,
        )
        num_threads = getattr(self._config, "cpu_threads", 4) or 4
        logger.info(
            "Loading Faster-Whisper model from: %s (device=%s, compute_type=%s, cpu_threads=%d)",
            target_model_path,
            self._config.device,
            self._config.compute_type,
            num_threads,
        )
        try:
            model = WhisperModel(
                target_model_path,
                device=self._config.device,
                compute_type=self._config.compute_type,
                cpu_threads=num_threads,
            )
        except Exception as primary_exc:
            if self._config.model_size != "base.en":
                logger.warning(
                    "Failed to load Faster-Whisper model '%s' on %s (%s). Falling back to 'base.en'...",
                    target_model_path,
                    self._config.device,
                    primary_exc,
                )
                try:
                    fallback_path = resolve_whisper_model_path(
                        model_size_or_name="base.en",
                        explicit_path=None,
                    )
                    model = WhisperModel(
                        fallback_path,
                        device=self._config.device,
                        compute_type=self._config.compute_type,
                        cpu_threads=num_threads,
                    )
                except Exception as fallback_exc:
                    logger.warning(
                        "Fallback model 'base.en' on %s failed (%s). Attempting CPU fallback...",
                        self._config.device,
                        fallback_exc,
                    )
                    try:
                        model = WhisperModel(
                            fallback_path,
                            device="cpu",
                            compute_type="int8",
                            cpu_threads=num_threads,
                        )
                    except Exception as cpu_exc:
                        raise RuntimeError(
                            "Whisper failure: both primary and fallback models failed to load."
                        ) from cpu_exc
            else:
                raise RuntimeError("Whisper failure.") from primary_exc

        with self._lock:
            self._model = model
            return self._model

    @staticmethod
    def _is_iris_response_text(text: str) -> bool:
        """Check if transcribed speech matches any canonical IRIS assistant response phrase."""
        if not text:
            return False
        norm = text.lower().strip()
        canonical_phrases = (
            "could you say it another way",
            "understand that command",
            "couldn't understand that command",
            "which browser would you like me to open",
            "chrome opened",
            "chrome closed",
            "notepad opened",
            "notepad closed",
            "camera opened",
            "camera closed",
            "done, sir",
            "couldn't complete that action",
            "couldn't complete that command",
            "response audio unavailable",
            "action blocked by actionengine",
        )
        for phrase in canonical_phrases:
            if phrase in norm:  # Only block if assistant speech is inside user phrase
                return True
        return False

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
