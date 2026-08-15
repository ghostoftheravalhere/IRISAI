"""Real-World User Experience Validation Script for IRIS AI V4 Conversational Agent."""

from __future__ import annotations

import logging
import time
from unittest.mock import MagicMock, patch

from backend.automation.action_models import ActionResult, CanonicalAction
from backend.brain.fusion import PerceptionEvent
from backend.config.settings import Settings
from backend.core.di.container import build_container
from backend.eye_tracking.calibration import EyeCenter
from backend.eye_tracking.gaze_service import GazeEstimate
from backend.perception.ambiguity_engine import CandidateMatch, AmbiguityResolution

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("validation")


def run_validation():
    settings = Settings(
        APP_ENV="testing",
        BRAIN_ORCHESTRATOR_ENABLED=True,
        FUSION_ENGINE_ENABLED=True,
    )
    container = build_container(settings)

    # Mock low-level OS side-effects to capture calls cleanly
    mock_click = MagicMock(return_value=True)
    mock_hotkey = MagicMock(return_value=True)
    mock_open_app = MagicMock(return_value=True)
    mock_close_win = MagicMock(return_value=True)
    mock_close_app = MagicMock(return_value=ActionResult(True, CanonicalAction.CLOSE_APPLICATION, "Closed"))
    mock_scroll = MagicMock(return_value=True)
    mock_press = MagicMock(return_value=True)
    mock_type_text = MagicMock(return_value=True)
    mock_move_rel = MagicMock(return_value=True)

    for ctrl in (container.desktop_controller, container.canonical_action_engine._desktop_controller):
        ctrl.click = mock_click
        ctrl.hotkey = mock_hotkey
        ctrl.open_application = mock_open_app
        ctrl.close_window = mock_close_win
        ctrl.close_application = mock_close_app
        ctrl.scroll = mock_scroll
        ctrl.press = mock_press
        ctrl.type_text = mock_type_text
        ctrl.move_rel = mock_move_rel

    pipeline = container.voice_pipeline
    dialogue = container.dialogue_manager
    ambiguity = container.ambiguity_engine
    fusion = container.fusion_engine
    orchestrator = container.brain_orchestrator

    results = []

    def record(scenario, phrase, expected, actual, pass_fail, failure_layer="", severity="NONE", recommendation=""):
        results.append({
            "scenario": scenario,
            "phrase": phrase,
            "expected": expected,
            "actual": actual,
            "pass_fail": pass_fail,
            "failure_layer": failure_layer,
            "severity": severity,
            "recommendation": recommendation,
        })
        print(f"[{pass_fail}] {scenario} | Phrase: '{phrase}' -> Actual: '{actual}'")

    # =========================================================================
    # SCENARIO 1 — NATURAL APP CONTROL
    # =========================================================================
    p1 = pipeline.execute("Open Chrome")
    record("SCENARIO 1", "Open Chrome", "Chrome opened", p1.message, "PASS" if p1.success else "FAIL")

    p2 = pipeline.execute("Launch Chrome")
    record("SCENARIO 1", "Launch Chrome", "Chrome opened", p2.message, "PASS" if p2.success else "FAIL")

    p3 = pipeline.execute("Can you open Chrome?")
    record("SCENARIO 1", "Can you open Chrome?", "Chrome opened", p3.message, "PASS" if p3.success else "FAIL")

    p4 = pipeline.execute("Take me to Chrome")
    record("SCENARIO 1", "Take me to Chrome", "Chrome opened", p4.message, "PASS" if p4.success else "FAIL")

    p5 = pipeline.execute("Open YouTube")
    record("SCENARIO 1", "Open YouTube", "YouTube opened", p5.message, "PASS" if p5.success else "FAIL")

    p6 = pipeline.execute("Go to YouTube")
    record("SCENARIO 1", "Go to YouTube", "YouTube opened", p6.message, "PASS" if p6.success else "FAIL")

    p7 = pipeline.execute("Switch to YouTube")
    record("SCENARIO 1", "Switch to YouTube", "YouTube opened", p7.message, "PASS" if p7.success else "FAIL")

    # =========================================================================
    # SCENARIO 2 — CONTEXTUAL FOLLOW-UP
    # =========================================================================
    s2_1 = pipeline.execute("Open Chrome")
    record("SCENARIO 2", "Open Chrome", "Chrome opened", s2_1.message, "PASS" if s2_1.success else "FAIL")

    s2_2 = pipeline.execute("Go to YouTube")
    record("SCENARIO 2", "Go to YouTube", "YouTube opened", s2_2.message, "PASS" if s2_2.success else "FAIL")

    s2_3 = pipeline.execute("Search for GTA 6")
    record("SCENARIO 2", "Search for GTA 6", "Browser search GTA 6", s2_3.message, "PASS" if s2_3.success else "FAIL")

    # Simulating UIA ambiguity for "Open the second result"
    c1 = CandidateMatch("GTA 6 Trailer 1", 300.0, 400.0, 0.75, "Search result", "link")
    c2 = CandidateMatch("GTA 6 Gameplay Leaks", 300.0, 500.0, 0.72, "Search result", "link")
    with patch.object(ambiguity, "resolve_candidates") as mock_res:
        mock_res.return_value = AmbiguityResolution("MULTIPLE_CANDIDATES", c1, (c1, c2), prompt_message="1. GTA 6 Trailer 1 2. GTA 6 Gameplay Leaks. Which one?")
        s2_4_prompt = pipeline.execute("Open result")
        s2_4 = pipeline.execute("Open the second result")
        pass_2_4 = s2_4.success and dialogue._last_resolved_target == "GTA 6 Gameplay Leaks"
        record("SCENARIO 2", "Open the second result", "Opens candidate #2 GTA 6 Gameplay Leaks", s2_4.message, "PASS" if pass_2_4 else "FAIL")

    s2_5 = pipeline.execute("Scroll down")
    record("SCENARIO 2", "Scroll down", "Scrolled down", s2_5.message, "PASS" if s2_5.success else "FAIL")

    gaze = GazeEstimate(eye_center=EyeCenter(0.5, 0.5), raw_x=500.0, raw_y=600.0, x=500.0, y=600.0, confidence=0.88, captured_at=time.time())
    with patch.object(container.eye_gaze, "get_latest_gaze", return_value=gaze):
        pevent = PerceptionEvent(source="voice", intent="PRIMARY_CLICK", confidence=1.0, raw_text="Open that")
        fused = fusion.ingest_event(pevent)
        orch_res = orchestrator.process_fusion_result(fused) if fused else None
        pass_2_6 = orch_res is not None and orch_res.success
        record("SCENARIO 2", "Open that", "Clicks gaze target (500, 600)", orch_res.message if orch_res else "No fusion result", "PASS" if pass_2_6 else "FAIL")

    # =========================================================================
    # SCENARIO 3 — CROSS-APPLICATION
    # =========================================================================
    s3_1 = pipeline.execute("Open VS Code")
    record("SCENARIO 3", "Open VS Code", "VS Code opened", s3_1.message, "PASS" if s3_1.success else "FAIL")

    s3_2 = pipeline.execute("Open my project")
    record("SCENARIO 3", "Open my project", "Project opened", s3_2.message, "PASS" if s3_2.success else "FAIL")

    s3_3 = pipeline.execute("Type hello")
    record("SCENARIO 3", "Type hello", "Typed 'hello'", s3_3.message, "PASS" if s3_3.success else "FAIL")

    s3_4 = pipeline.execute("Save it")
    record("SCENARIO 3", "Save it", "Saved (ctrl+s)", s3_4.message, "PASS" if s3_4.success else "FAIL")

    s3_5 = pipeline.execute("Close this")
    record("SCENARIO 3", "Close this", "Closed project window", s3_5.message, "PASS" if s3_5.success else "FAIL")

    s3_6 = pipeline.execute("Open Notepad")
    record("SCENARIO 3", "Open Notepad", "Notepad opened", s3_6.message, "PASS" if s3_6.success else "FAIL")

    s3_7 = pipeline.execute("Paste it")
    record("SCENARIO 3", "Paste it", "Pasted clipboard (ctrl+v)", s3_7.message, "PASS" if s3_7.success else "FAIL")

    # Check that context did not leak VS Code target into Notepad
    pass_s3 = (dialogue._last_active_app == "notepad")
    record("SCENARIO 3", "Cross-App Context Isolation", "Active app is notepad, not vscode", f"active_app={dialogue._last_active_app}", "PASS" if pass_s3 else "FAIL")

    # =========================================================================
    # SCENARIO 4 — AMBIGUITY
    # =========================================================================
    c_rep1 = CandidateMatch("Q3 Financial Report.docx", 100.0, 200.0, 0.70, "Fuzzy match", "document")
    c_rep2 = CandidateMatch("Annual Audit Report.pdf", 100.0, 300.0, 0.68, "Fuzzy match", "document")
    with patch.object(ambiguity, "resolve_candidates") as mock_res:
        mock_res.return_value = AmbiguityResolution("MULTIPLE_CANDIDATES", c_rep1, (c_rep1, c_rep2), prompt_message="1. Q3 Financial Report.docx 2. Annual Audit Report.pdf. Which one?")
        s4_prompt = pipeline.execute("Open report")
        record("SCENARIO 4", "Open report (multiple matches)", "Presents 2 candidates and asks prompt", s4_prompt.message, "PASS" if "Which one?" in s4_prompt.message else "FAIL")

    s4_ans = pipeline.execute("first one")
    record("SCENARIO 4", "first one", "Resolves to candidate #1 Q3 Financial Report.docx", s4_ans.message, "PASS" if s4_ans.success else "FAIL")

    # =========================================================================
    # SCENARIO 5 — REFERENTIAL LANGUAGE
    # =========================================================================
    with patch.object(container.eye_gaze, "get_latest_gaze", return_value=gaze):
        pe1 = PerceptionEvent(source="voice", intent="PRIMARY_CLICK", confidence=1.0, raw_text="Click this")
        f1 = orchestrator.process_fusion_result(fusion.ingest_event(pe1))
        record("SCENARIO 5", "Click this", "Left click at gaze", f1.message, "PASS" if f1.success else "FAIL")

        pe2 = PerceptionEvent(source="voice", intent="RIGHT_CLICK", confidence=1.0, raw_text="Right click here")
        f2 = orchestrator.process_fusion_result(fusion.ingest_event(pe2))
        record("SCENARIO 5", "Right click here", "Right click at gaze", f2.message, "PASS" if f2.success else "FAIL")

    s5_3 = pipeline.execute("Copy it")
    record("SCENARIO 5", "Copy it", "Executes ctrl+c", s5_3.message, "PASS" if s5_3.success else "FAIL")

    s5_4 = pipeline.execute("Paste that")
    record("SCENARIO 5", "Paste that", "Executes ctrl+v", s5_4.message, "PASS" if s5_4.success else "FAIL")

    s5_5 = pipeline.execute("Close this")
    record("SCENARIO 5", "Close this", "Closes window", s5_5.message, "PASS" if s5_5.success else "FAIL")

    # =========================================================================
    # SCENARIO 6 — ACCESSIBILITY / VOICE-ONLY
    # =========================================================================
    sc6_tests = [
        ("Click", "PRIMARY_CLICK", "click"),
        ("Right click", "RIGHT_CLICK", "right_click"),
        ("Double click", "DOUBLE_CLICK", "double_click"),
        ("Scroll down", "SCROLL_DOWN", "scroll"),
        ("Start selecting", "START_SELECTING", "start_selecting"),
        ("Stop selecting", "STOP_SELECTING", "stop_selecting"),
        ("Copy", "COPY", "copy"),
        ("Paste", "PASTE", "paste"),
        ("Type hello", "TYPE_TEXT", "type"),
        ("Close this", "CLOSE_WINDOW", "close"),
        ("Minimize window", "MINIMIZE_WINDOW", "minimize"),
    ]
    for cmd, intent_type, name in sc6_tests:
        r = pipeline.execute(cmd)
        record("SCENARIO 6", f"Voice-only {cmd}", f"Executes {name}", r.message, "PASS" if r.success else "FAIL")

    # =========================================================================
    # SCENARIO 7 — FAILURE HANDLING
    # =========================================================================
    # Unknown target
    s7_1 = pipeline.execute("Open NonexistentApp9999")
    record("SCENARIO 7", "Open NonexistentApp9999", "Attempts app open gracefully", s7_1.message, "PASS" if s7_1.success or "Failed" in s7_1.message or "opened" in s7_1.message else "FAIL")

    # Low confidence ambiguity prompt
    c_low = CandidateMatch("Uncertain App", 100.0, 100.0, 0.58, "Low score", "window")
    with patch.object(ambiguity, "resolve_candidates") as mock_res:
        mock_res.return_value = AmbiguityResolution("MEDIUM_CONFIDENCE", c_low, (c_low,), prompt_message="I found 'Uncertain App'. Do you want me to open it?")
        s7_2 = pipeline.execute("Open uncertain")
        record("SCENARIO 7", "Low confidence target", "Asks confirmation prompt", s7_2.message, "PASS" if "Do you want me to open it?" in s7_2.message else "FAIL")

    # Stale gaze fallback
    old_gaze = GazeEstimate(eye_center=EyeCenter(0.5, 0.5), raw_x=100.0, raw_y=100.0, x=100.0, y=100.0, confidence=0.88, captured_at=time.time() - 10.0)
    with patch.object(container.eye_gaze, "get_latest_gaze", return_value=old_gaze):
        pe_stale = PerceptionEvent(source="voice", intent="PRIMARY_CLICK", confidence=1.0, raw_text="Click here")
        f_stale = fusion.ingest_event(pe_stale)
        pass_s7_3 = f_stale is None or f_stale.target is None or f_stale.combined_confidence < 0.5
        record("SCENARIO 7", "Stale gaze event", "Rejects stale gaze (>2s old)", "Rejected stale gaze" if pass_s7_3 else "Accepted stale gaze", "PASS" if pass_s7_3 else "FAIL", failure_layer="gaze", severity="MEDIUM", recommendation="Check gaze timestamp cutoff in FusionEngine")

    print("\nValidation Summary:")
    passed_count = sum(1 for r in results if r["pass_fail"] == "PASS")
    total_count = len(results)
    print(f"Total Scenarios Tested: {total_count}")
    print(f"Total Passed: {passed_count} / {total_count}")

    return results


if __name__ == "__main__":
    run_validation()
