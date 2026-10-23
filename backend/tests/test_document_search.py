"""Tests for Local Document Search Engine, Intent Parsing, and Async Execution."""

import io
import os
from pathlib import Path
import time
from typing import Any
import pytest

from backend.features.document_search import (
    DocumentSearcher,
    DocumentSearchService,
    open_document,
)
from backend.voice.command_engine import (
    COMMAND_GRAMMAR,
    VoskCommandEngine,
    clean_doc_search_query,
    extract_document_search_intent,
)
from backend.voice.command_parser import (
    IntentParserService,
    VoiceIntentType,
)


def _generate_valid_pdf(text: str) -> bytes:
    """Generate minimal valid PDF bytes containing text with precise xref offsets."""
    content = f"BT /F1 12 Tf 72 712 Td ({text}) Tj ET".encode("latin-1")
    stream_len = len(content)
    obj4 = (
        f"4 0 obj\n<< /Length {stream_len} >>\nstream\n".encode("latin-1")
        + content
        + b"\nendstream\nendobj\n"
    )
    header = b"%PDF-1.4\n"
    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    obj5 = b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"

    offsets = [0]
    curr = len(header)
    for obj in [obj1, obj2, obj3, obj4, obj5]:
        offsets.append(curr)
        curr += len(obj)
    xref_offset = curr
    xref = b"xref\n0 6\n0000000000 65535 f \n"
    for off in offsets[1:]:
        xref += f"{off:010d} 00000 n \n".encode("latin-1")
    trailer = f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("latin-1")
    return header + obj1 + obj2 + obj3 + obj4 + obj5 + xref + trailer


class MockSpeechManager:
    """Captures spoken text for assertion."""

    def __init__(self) -> None:
        self.spoken: list[str] = []

    def speak(self, text: str) -> float:
        self.spoken.append(text)
        return 50.0


# ── Search Engine Format Extraction Tests ─────────────────────────────────────

def test_document_searcher_formats(tmp_path: Path):
    """Verify that matching is strictly based on file and folder names, and body text is ignored."""
    # 1. Matching text file
    txt_file = tmp_path / "quantum_notes.txt"
    txt_file.write_text("Regular content without target keyword.", encoding="utf-8")

    # 2. Matching markdown file
    md_file = tmp_path / "quantum_readme.md"
    md_file.write_text("More content.", encoding="utf-8")

    # 3. Matching folder
    folder = tmp_path / "quantum_research"
    folder.mkdir()

    # 4. Non-matching file whose BODY contains the keyword (MUST BE IGNORED)
    body_only_file = tmp_path / "unrelated_document.txt"
    body_only_file.write_text("This file body mentions quantum entanglement multiple times.", encoding="utf-8")

    searcher = DocumentSearcher(target_dir=tmp_path)
    results = searcher.search("quantum")

    assert len(results) == 3
    file_names = {r["file_name"] for r in results}
    assert file_names == {"quantum_notes.txt", "quantum_readme.md", "quantum_research"}
    assert "unrelated_document.txt" not in file_names

    for r in results:
        assert "file_path" in r
        assert Path(r["file_path"]).exists()
        assert len(r["matches"]) == 1
        if r["file_name"] == "quantum_research":
            assert r["is_directory"] is True
            assert r["matches"][0]["location"] == "Folder"
        else:
            assert r["is_directory"] is False
            assert r["matches"][0]["location"] == "Filename"


def test_document_searcher_exact_match_prioritization(tmp_path: Path):
    """Verify exact matches (e.g., MPC.txt or folder MPC) rank higher than partial matches."""
    (tmp_path / "sample_mpc_v2.log").write_text("data", encoding="utf-8")
    (tmp_path / "MPC.txt").write_text("data", encoding="utf-8")
    mpc_folder = tmp_path / "MPC"
    mpc_folder.mkdir()

    searcher = DocumentSearcher(target_dir=tmp_path)
    results = searcher.search("MPC")

    assert len(results) == 3
    # Exact matches (MPC.txt and MPC) must rank higher than substring match (sample_mpc_v2.log)
    top_two = {results[0]["file_name"], results[1]["file_name"]}
    assert "MPC.txt" in top_two
    assert "MPC" in top_two
    assert results[2]["file_name"] == "sample_mpc_v2.log"


def test_document_searcher_directory_exclusion(tmp_path: Path):
    """Verify heavy directories like .git, node_modules, .venv, AppData are skipped."""
    valid_file = tmp_path / "valid_AlphaOmega.txt"
    valid_file.write_text("Regular content.", encoding="utf-8")

    # Excluded directories
    for ex_dir in [".git", "node_modules", "__pycache__", "venv", ".venv", "dist", "build", "AppData"]:
        sub = tmp_path / ex_dir
        sub.mkdir(parents=True, exist_ok=True)
        ignored = sub / "ignored_AlphaOmega.txt"
        ignored.write_text("Regular content.", encoding="utf-8")

    searcher = DocumentSearcher(target_dir=tmp_path)
    results = searcher.search("AlphaOmega")

    assert len(results) == 1
    assert results[0]["file_name"] == "valid_AlphaOmega.txt"


def test_document_searcher_multi_root_and_system_exclusions(tmp_path: Path):
    """Verify multi-root target dirs, secondary drive detection, and system exclusions."""
    # Test default multi-root directories
    searcher_default = DocumentSearcher()
    assert any("Documents" in str(p) for p in searcher_default.target_dirs)
    assert any("Desktop" in str(p) for p in searcher_default.target_dirs)
    assert any("Downloads" in str(p) for p in searcher_default.target_dirs)

    # Test custom multi-root directory list
    dir_a = tmp_path / "root_a"
    dir_b = tmp_path / "root_b"
    dir_a.mkdir()
    dir_b.mkdir()
    (dir_a / "file_a_Unique.txt").write_text("Sample", encoding="utf-8")
    (dir_b / "file_b_Unique.txt").write_text("Sample", encoding="utf-8")

    # Add system-excluded directories
    for sys_name in ["$recycle.bin", "System Volume Information", "Windows", "Program Files", "Program Files (x86)", "temp", ".hidden"]:
        sub = dir_a / sys_name
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "ignored_Unique.txt").write_text("Sample", encoding="utf-8")

    searcher = DocumentSearcher(target_dirs=[dir_a, dir_b])
    results = searcher.search("Unique")

    assert len(results) == 2
    found_names = {r["file_name"] for r in results}
    assert found_names == {"file_a_Unique.txt", "file_b_Unique.txt"}


def test_document_searcher_permission_handling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify PermissionError and OSError are gracefully caught during directory walk."""
    good_dir = tmp_path / "good_dir"
    good_dir.mkdir()
    (good_dir / "valid_target.txt").write_text("Accessible file content query.", encoding="utf-8")

    bad_dir = tmp_path / "bad_dir"
    bad_dir.mkdir()

    # Create a searcher targeting both a non-existent drive and good_dir
    fake_drive = Path("Z:\\")
    searcher = DocumentSearcher(target_dirs=[fake_drive, bad_dir, good_dir])

    # Monkeypatch os.walk on bad_dir to raise PermissionError
    orig_os_walk = os.walk
    def mock_os_walk(top, *args, **kwargs):
        if str(top) == str(bad_dir):
            raise PermissionError("Access is denied to bad_dir")
        return orig_os_walk(top, *args, **kwargs)

    monkeypatch.setattr(os, "walk", mock_os_walk)

    results = searcher.search("valid_target")
    assert len(results) == 1
    assert results[0]["file_name"] == "valid_target.txt"


def test_document_searcher_limits(tmp_path: Path):
    """Verify max results limit stops traversal."""
    # Create 8 matching files
    for i in range(8):
        f = tmp_path / f"target_doc_{i}.txt"
        f.write_text("Content", encoding="utf-8")

    searcher = DocumentSearcher(target_dir=tmp_path, max_results=3)
    results = searcher.search("target_doc")

    assert len(results) == 3



# ── Regex Intent Extraction & Grammar Integration Tests ───────────────────────

def test_regex_document_search_patterns():
    """Verify regex-based intent extraction patterns from user requests."""
    # Pattern 1: (?:search for|find|look for) (.*?) in (?:my )?(?:documents|docs|files)
    assert extract_document_search_intent("search for budget report in my documents") == "budget report"
    assert extract_document_search_intent("find quarterly revenue in documents") == "quarterly revenue"
    assert extract_document_search_intent("look for kinematic physics in files") == "kinematic physics"
    assert extract_document_search_intent("find contract in my docs") == "contract"

    # Pattern 2: search (?:documents|docs|files) for (.*?)$
    assert extract_document_search_intent("search documents for budget report") == "budget report"
    assert extract_document_search_intent("search files for machine learning") == "machine learning"
    assert extract_document_search_intent("search docs for meeting notes") == "meeting notes"

    # Strip punctuation and filler words
    assert extract_document_search_intent("search documents for the quarterly earnings!") == "quarterly earnings"
    assert extract_document_search_intent("please search files for a project plan.") == "project plan"


def test_command_engine_grammar_coexistence():
    """Verify VoskCommandEngine respects document search without breaking existing grammar."""
    engine = VoskCommandEngine(model_path=None)

    # Standard grammar commands must match exactly
    for cmd in ["click", "double click", "start dictation", "scroll down", "minimize"]:
        assert engine.process_text_command(cmd) == cmd

    # Document search commands must extract query and not collide with grammar words
    assert engine.process_text_command("search documents for financial report") == "search documents for financial report"
    assert engine.extract_document_search("search documents for financial report") == "financial report"

    # Grammar words embedded inside search queries (e.g. 'type' or 'click')
    assert engine.extract_document_search("search documents for type") == "type"
    assert engine.extract_document_search("find click in my documents") == "click"

    # Unrelated text
    assert engine.process_text_command("completely unrelated random speech") is None
    assert engine.process_text_command("") is None


def test_intent_parser_integration():
    """Verify IntentParserService outputs DOCUMENT_SEARCH and OPEN_FILE VoiceIntent objects."""
    parser = IntentParserService()

    intent_doc = parser.parse("search documents for quarterly report")
    assert intent_doc.intent == VoiceIntentType.DOCUMENT_SEARCH
    assert intent_doc.query == "quarterly report"

    intent_find = parser.parse("find annual budget in my files")
    assert intent_find.intent == VoiceIntentType.DOCUMENT_SEARCH
    assert intent_find.query == "annual budget"

    intent_open = parser.parse("open file")
    assert intent_open.intent == VoiceIntentType.OPEN_FILE

    intent_open_the = parser.parse("open the document")
    assert intent_open_the.intent == VoiceIntentType.OPEN_FILE


# ── Threaded Execution & Spoken Feedback Tests ────────────────────────────────

def test_document_search_service_async(tmp_path: Path):
    """Verify non-blocking threaded execution, acknowledgment, completion speech, and WebSocket broadcast."""
    doc_file = tmp_path / "budget_2026.txt"
    doc_file.write_text("Approved project budget is 50000 USD.", encoding="utf-8")

    searcher = DocumentSearcher(target_dir=tmp_path)
    mock_speech = MockSpeechManager()
    broadcast_events: list[dict[str, Any]] = []

    def mock_broadcast(event: dict[str, Any]):
        broadcast_events.append(event)

    service = DocumentSearchService(
        searcher=searcher,
        speech_manager=mock_speech,
        broadcast_callback=mock_broadcast,
    )

    # Case 1: Match found
    thread = service.search_async("budget", acknowledge=True)
    thread.join(timeout=3.0)

    # Verify spoken messages
    assert len(mock_speech.spoken) == 2
    assert mock_speech.spoken[0] == "Searching documents for budget."
    assert mock_speech.spoken[1] == "Found matching item budget_2026.txt."


    # Verify WebSocket broadcast event
    assert len(broadcast_events) == 1
    ev = broadcast_events[0]
    assert ev["event_type"] == "DOCUMENT_SEARCH_RESULTS"
    assert ev["query"] == "budget"
    assert ev["count"] == 1
    assert ev["top_result"]["file_name"] == "budget_2026.txt"
    assert service.latest_result_path == str(doc_file.resolve())

    # Case 2: Zero matches found
    mock_speech.spoken.clear()
    broadcast_events.clear()

    thread_zero = service.search_async("nonexistent_term", acknowledge=True)
    thread_zero.join(timeout=3.0)

    assert len(mock_speech.spoken) == 2
    assert mock_speech.spoken[0] == "Searching documents for nonexistent_term."
    assert mock_speech.spoken[1] == "I couldn't find any documents mentioning nonexistent_term."
    assert broadcast_events[0]["count"] == 0
    assert service.latest_result_path is None


def test_document_search_auto_launches_top_match(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify DocumentSearchService auto-invokes open_document on top match with select_in_explorer=True."""
    doc = tmp_path / "unique_keyword_target.txt"
    doc.write_text("File content.", encoding="utf-8")

    opened_paths = []

    def mock_open_document(target, select_in_explorer=True):
        opened_paths.append((str(target), select_in_explorer))
        return True

    from backend.features import document_search
    monkeypatch.setattr(document_search, "open_document", mock_open_document)

    searcher = DocumentSearcher(target_dir=tmp_path)
    service = DocumentSearchService(searcher=searcher)

    thread = service.search_async("Unique keyword", acknowledge=False)
    thread.join(timeout=3.0)

    assert len(opened_paths) == 1
    assert opened_paths[0] == (str(doc.resolve()), True)
    assert service.latest_result_path == str(doc.resolve())



def test_open_document_helper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify open_document helper launches explorer /select for files and explorer for folders."""
    # Non-existent file returns False
    assert open_document(tmp_path / "missing.pdf") is False

    # Existing file path validation
    real_file = tmp_path / "sample.txt"
    real_file.write_text("Hello world", encoding="utf-8")
    assert real_file.exists()

    popen_cmds = []

    def mock_popen(cmd, *args, **kwargs):
        popen_cmds.append(cmd)
        return None

    import subprocess
    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    # 1. File with select_in_explorer=True (default)
    assert open_document(real_file) is True
    assert len(popen_cmds) == 1
    norm_file = os.path.normpath(str(real_file.resolve()))
    assert popen_cmds[0] == f'explorer /select,"{norm_file}"'

    # 2. File with select_in_explorer=False
    popen_cmds.clear()
    assert open_document(real_file, select_in_explorer=False) is True
    assert len(popen_cmds) == 1
    assert popen_cmds[0] == f'explorer "{norm_file}"'

    # 3. Directory (folder)
    popen_cmds.clear()
    assert open_document(tmp_path) is True
    assert len(popen_cmds) == 1
    norm_dir = os.path.normpath(str(tmp_path.resolve()))
    assert popen_cmds[0] == f'explorer "{norm_dir}"'

    # 4. Exception handling
    def mock_popen_fail(cmd, *args, **kwargs):
        raise OSError("Explorer process launch failed")

    monkeypatch.setattr(subprocess, "Popen", mock_popen_fail)
    assert open_document(real_file) is False



# ── Robust Query Extraction & Stutter Handling Tests ─────────────────────────

def test_robust_query_extraction_and_stutter_handling():
    """Verify clean query extraction when user repeats prefixes or stutters."""
    # Exact cases required:
    # "Find in file, find MPC," -> "MPC"
    assert extract_document_search_intent("Find in file, find MPC,") == "MPC"
    assert clean_doc_search_query("Find in file, find MPC,") == "MPC"

    # "search files find physics" -> "physics"
    assert extract_document_search_intent("search files find physics") == "physics"
    assert clean_doc_search_query("search files find physics") == "physics"

    # "search files search report" -> "report"
    assert extract_document_search_intent("search files search report") == "report"
    assert clean_doc_search_query("search files search report") == "report"

    # "find in documents MPC" -> "MPC"
    assert extract_document_search_intent("find in documents MPC") == "MPC"
    assert clean_doc_search_query("find in documents MPC") == "MPC"

    # Additional stutters
    assert extract_document_search_intent("search in files search MPC") == "MPC"
    assert extract_document_search_intent("find in file find MPC") == "MPC"


# ── Voice Recognition Busy Lock Tests ─────────────────────────────────────────

def test_voice_recognition_service_busy_lock():
    """Verify voice recognition service busy lock ignores/discards audio during active search."""
    from backend.voice.recognizer import VoiceRecognitionService, VoiceRecognitionConfig

    callback_invoked = []
    service = VoiceRecognitionService(
        VoiceRecognitionConfig(),
        on_transcript=lambda t: callback_invoked.append(t),
    )
    assert service.is_busy() is False
    assert service._should_capture() is True

    # Engage busy lock
    service.set_busy(True)
    assert service.is_busy() is True
    # In continuous mode, capture should be suppressed when busy
    assert service._should_capture() is False

    # Dispatching audio while busy should be immediately dropped
    import numpy as np
    dummy_audio = np.zeros(16000, dtype=np.float32)
    service._handle_audio(dummy_audio)
    assert len(callback_invoked) == 0

    # Release busy lock
    service.set_busy(False)
    assert service.is_busy() is False
    assert service._should_capture() is True


# ── UI Conversation Log & Assistant Message Publishing Tests ──────────────────

class MockVoiceService:
    def __init__(self) -> None:
        self._is_busy: bool = False

    def set_busy(self, busy: bool) -> None:
        self._is_busy = busy

    def is_busy(self) -> bool:
        return self._is_busy


def test_document_search_service_busy_lock_and_ui_log_push(tmp_path: Path):
    """Verify busy lock lifecycle and assistant message push to EventBus and WebSocket."""
    doc_file = tmp_path / "mpc_notes.txt"
    doc_file.write_text("Kinematic model predictive control MPC trajectory optimization.", encoding="utf-8")

    searcher = DocumentSearcher(target_dir=tmp_path)
    mock_speech = MockSpeechManager()
    mock_voice = MockVoiceService()
    published_events = []

    class MockEventBus:
        def publish(self, event):
            published_events.append(event)

    broadcast_events: list[dict[str, Any]] = []

    service = DocumentSearchService(
        searcher=searcher,
        speech_manager=mock_speech,
        broadcast_callback=lambda ev: broadcast_events.append(ev),
        event_bus=MockEventBus(),
        voice_service=mock_voice,
    )

    # 1. Match found: verify busy lock active during search and released after completion
    thread = service.search_async("MPC", acknowledge=True)
    assert mock_voice.is_busy() is True
    thread.join(timeout=3.0)
    assert mock_voice.is_busy() is False

    # Verify EventBus received AutomationExecutedEvent with formatted assistant message
    assert len(published_events) == 1
    ev = published_events[0]
    assert ev.intent == "DOCUMENT_SEARCH"
    assert ev.action == "DOCUMENT_SEARCH"
    assert ev.success is True
    assert "Found matches for 'MPC' in 1 item(s):" in ev.execution_status
    assert "• 📄 mpc_notes.txt" in ev.execution_status
    assert "mpc_notes.txt" in ev.execution_status


    # Verify WebSocket broadcast contains the assistant message
    assert len(broadcast_events) == 1
    assert broadcast_events[0]["message"] == ev.execution_status

    # 2. No matches: verify assistant message formatting for empty result
    published_events.clear()
    broadcast_events.clear()

    thread_zero = service.search_async("nonexistent_quantum_query", acknowledge=False)
    thread_zero.join(timeout=3.0)
    assert mock_voice.is_busy() is False

    assert len(published_events) == 1
    zero_ev = published_events[0]
    expected_no_match = "No documents found matching 'nonexistent_quantum_query' across Desktop, Documents, or Downloads."
    assert zero_ev.execution_status == expected_no_match
    assert broadcast_events[0]["message"] == expected_no_match


# ── Search Timeout Guard Tests ────────────────────────────────────────────────

def test_document_searcher_timeout_guard(tmp_path: Path):
    """Verify DocumentSearcher.search terminates within the timeout limit."""
    for i in range(10):
        (tmp_path / f"doc_{i}.txt").write_text(f"Sample data content {i}", encoding="utf-8")

    searcher = DocumentSearcher(target_dir=tmp_path)
    # Search with very small timeout returns quickly without hanging
    t0 = time.time()
    results = searcher.search("content", timeout_seconds=0.0001)
    duration = time.time() - t0
    assert duration < 1.0
    assert isinstance(results, list)

