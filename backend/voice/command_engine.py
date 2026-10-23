"""Constrained Vosk Command Engine for low-latency (<80ms) multimodal gaze action recognition."""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any
import numpy as np

from backend.core.config.settings import settings, APP_DATA_DIR
from backend.utils.logger import get_logger

logger = get_logger(__name__)

DOC_SEARCH_PATTERNS = [
    re.compile(r"^search\s+(?:documents|docs|files|file|system|pc)\s+for\s+(.*?)[?!.]*$", re.IGNORECASE),
    re.compile(r"^in\s+(?:my\s+)?(?:documents|docs|files|file|system|pc)[,\s]+(?:find|search for|look for|search)\s+(.*?)[?!.]*$", re.IGNORECASE),
    re.compile(r"^(?:find|search for|look for|search)\s+(?:for\s+)?([^.]+?)(?:\s+in\s+(?:my\s+)?(?:documents|docs|files|file|system|pc))[?!.]*$", re.IGNORECASE),
    re.compile(r"^(?:find|search for|look for|search)\s+(?:for\s+)?([^.]+?)[?!.]*$", re.IGNORECASE),
]


def clean_doc_search_query(raw_query: str) -> str:
    """Strip punctuation, redundant command prefixes, and stuttered keywords from extracted query string."""
    if not raw_query:
        return ""
    query = raw_query.strip().strip(".,?!'\"")
    query = re.sub(r"^(?:the|a|an|please|can you|could you)\s+", "", query, flags=re.IGNORECASE).strip()

    # Iteratively strip repeated search/find/in file phrases until stable
    prev = None
    while prev != query:
        prev = query
        # Strip repeated search/find/in file phrases (e.g. "find in file, find MPC")
        query = re.sub(
            r'^(?:find|search(?: for)?|look for)\s+(?:in\s+(?:file|files|doc|docs|documents|system|pc)[,\s]+)?(?:find|search(?: for)?|look for)?\s*',
            '',
            query,
            flags=re.IGNORECASE,
        ).strip().strip(".,?!'\"")

        query = re.sub(
            r'^(?:in\s+(?:file|files|doc|docs|documents|system|pc)[,\s]+)',
            '',
            query,
            flags=re.IGNORECASE,
        ).strip().strip(".,?!'\"")

        query = re.sub(
            r'^(?:file|files|documents|docs|system|pc)\s+(?:for\s+)?(?:find|search(?: for)?|look for)\s*',
            '',
            query,
            flags=re.IGNORECASE,
        ).strip().strip(".,?!'\"")

        query = re.sub(
            r'^(?:find|search(?: for)?|look for|for)\s+',
            '',
            query,
            flags=re.IGNORECASE,
        ).strip().strip(".,?!'\"")

        query = re.sub(
            r'\s+in\s+(?:my\s+)?(?:file|files|doc|docs|documents|system|pc)$',
            '',
            query,
            flags=re.IGNORECASE,
        ).strip().strip(".,?!'\"")

    return query.strip(".,?!'\"")


def extract_document_search_intent(text: str) -> str | None:
    """
    Extract clean query from document search patterns:
    - (?:find|search for|look for|search) <query> [in my documents/docs/files/system/pc]
    - search (?:documents|docs|files|system|pc) for <query>
    """
    if not text:
        return None
    trimmed = text.strip()
    # Strip conversational/polite prefixes before pattern matching
    trimmed = re.sub(r"^(?:please|can you|could you|hey iris|iris|i want to|i'd like to)\s+", "", trimmed, flags=re.IGNORECASE).strip()
    lower = trimmed.lower()
    # Route web searches targeting chrome/edge/browser to browser search
    if any(b in lower for b in ("chrome", "edge", "google", "browser")):
        if not any(d in lower for d in ("documents", "docs", "files", "system", "pc")):
            return None
    for pattern in DOC_SEARCH_PATTERNS:
        match = pattern.search(trimmed)
        if match:
            clean_q = clean_doc_search_query(match.group(1))
            if clean_q:
                return clean_q
    return None

COMMAND_GRAMMAR: list[str] = [
    # Mouse Look & Say (Phase 1 & 2)
    "click",
    "tap",
    "right click",
    "double click",
    "hold",
    "drag",
    "release",
    "drop",
    "scroll up",
    "scroll down",
    "stop",
    # Dictation (Phase 3)
    "type",
    "start dictation",
    "stop dictation",
    # OS & Window Control (Phase 4)
    "minimize",
    "maximize",
    "close window",
    "switch app",
    "show desktop",
    "new tab",
    "close tab",
]


def resolve_vosk_model_path(explicit_path: str | None = None) -> str | None:
    """
    Locates the Vosk model directory.
    Resolution order:
    1. explicit_path if provided and exists
    2. settings.VOSK_MODEL_PATH if set and exists
    3. User-space data dir: %LOCALAPPDATA%/IRISAI/models/vosk (or APP_DATA_DIR / models / vosk)
    4. Bundled production resources
    """
    if explicit_path and os.path.exists(explicit_path):
        return explicit_path

    if settings.VOSK_MODEL_PATH and os.path.exists(settings.VOSK_MODEL_PATH):
        return settings.VOSK_MODEL_PATH

    user_space_vosk = os.path.join(str(APP_DATA_DIR), "models", "vosk")
    if os.path.exists(user_space_vosk):
        return user_space_vosk

    local_appdata = os.getenv("LOCALAPPDATA")
    if local_appdata:
        candidate = os.path.join(local_appdata, "IRISAI", "models", "vosk")
        if os.path.exists(candidate):
            return candidate

    search_dirs: list[str] = []
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        meipass = getattr(sys, "_MEIPASS", exe_dir)
        search_dirs.extend([
            os.path.join(meipass, "resources", "models", "vosk"),
            os.path.join(exe_dir, "resources", "models", "vosk"),
        ])

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    search_dirs.append(os.path.join(repo_root, "resources", "models", "vosk"))

    for sdir in search_dirs:
        if os.path.exists(sdir):
            return sdir

    return None


class VoskCommandEngine:
    """
    Constrained Vosk Speech Recognizer for real-time gaze action commands.
    Targets <80ms recognition latency using restricted grammar list.
    Includes a graceful fallback/mock mode when Vosk or model is not installed/present.
    """

    def __init__(self, model_path: str | None = None, sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        self.grammar = COMMAND_GRAMMAR
        self.ready = False
        self.mock_mode = False
        self._model: Any | None = None
        self._recognizer: Any | None = None

        resolved_path = resolve_vosk_model_path(model_path)
        self.model_path = resolved_path

        self._initialize_vosk(resolved_path)

    def _initialize_vosk(self, path: str | None) -> None:
        if not path or not os.path.exists(path):
            logger.warning("[VOSK] Model path not found (%s). Entering graceful mock/fallback mode.", path)
            self.mock_mode = True
            return

        try:
            import vosk
            vosk.SetLogLevel(-1)
            self._model = vosk.Model(path)
            grammar_json = json.dumps(self.grammar)
            self._recognizer = vosk.KaldiRecognizer(self._model, self.sample_rate, grammar_json)
            self.ready = True
            logger.info("[VOSK] Command Engine initialized successfully from %s", path)
        except Exception as err:
            logger.warning("[VOSK] Failed to initialize Vosk recognizer (%s). Entering mock/fallback mode.", err)
            self.mock_mode = True

    def process_audio_chunk(self, pcm_float32: np.ndarray) -> str | None:
        """
        Process a 16kHz mono float32 audio chunk and return a recognized command if present.
        """
        if not self.ready or self.mock_mode or self._recognizer is None:
            return None

        if pcm_float32.size == 0:
            return None

        # Convert float32 [-1.0, 1.0] to int16 PCM bytes
        pcm_int16 = (np.clip(pcm_float32, -1.0, 1.0) * 32767.0).astype(np.int16)
        pcm_bytes = pcm_int16.tobytes()

        try:
            if self._recognizer.AcceptWaveform(pcm_bytes):
                res = json.loads(self._recognizer.Result())
                text = res.get("text", "").strip()
            else:
                res = json.loads(self._recognizer.PartialResult())
                text = res.get("partial", "").strip()

            return self.process_text_command(text)
        except Exception as err:
            logger.debug("[VOSK] Error processing audio chunk: %s", err)
            return None

    def extract_document_search(self, raw_text: str) -> str | None:
        """Extract clean query from document search patterns if present."""
        return extract_document_search_intent(raw_text)

    def process_text_command(self, raw_text: str) -> str | None:
        """
        Match and parse raw text string directly against COMMAND_GRAMMAR.
        Checked alongside existing command grammar without breaking prioritized multi-word tokens.
        """
        if not raw_text:
            return None

        # Check document search intent first so that keywords inside search queries
        # (e.g. 'search documents for type' or 'find click in files') are not misclassified
        # as low-level mouse/dictation actions.
        doc_query = extract_document_search_intent(raw_text)
        if doc_query:
            return f"search documents for {doc_query}"

        cleaned = raw_text.strip().lower()

        # Direct match check
        if cleaned in self.grammar:
            return cleaned

        # Word substring/token check in case of extra noise or partials (sort by length descending)
        for cmd in sorted(self.grammar, key=len, reverse=True):
            if cmd in cleaned:
                return cmd

        return None
