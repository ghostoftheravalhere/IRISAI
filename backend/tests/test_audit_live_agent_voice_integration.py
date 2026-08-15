"""Empirical Read-Only Integration Audit for Agent Core Live Voice Pipeline."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from backend.config.settings import Settings
from backend.core.di.container import build_container
from backend.automation.action_engine import CanonicalAction
from backend.voice.command_parser import VoiceIntentType


def audit_live_voice_pipeline():
    """Audit the real live AppContainer runtime for AgentCore routing."""
    print("=" * 80)
    print("IRIS AI V4 — AGENT CORE LIVE VOICE INTEGRATION AUDIT")
    print("=" * 80)

    settings = Settings(APP_ENV="testing")
    container = build_container(settings)

    # Mock desktop controller PyAutoGUI typing to prevent physical mouse failsafe
    container.desktop_controller.type_text = MagicMock(return_value=True)

    # 1. Audit AppContainer fields
    print("\n--- 1. AppContainer Service Audit ---")
    has_agent_core = hasattr(container, "agent_core") and container.agent_core is not None
    print(f"AppContainer has agent_core: {has_agent_core}")

    orch = container.brain_orchestrator
    has_agent_core_in_orch = hasattr(orch, "_agent_core") and getattr(orch, "_agent_core") is not None
    print(f"BrainOrchestrator has _agent_core: {has_agent_core_in_orch}")

    pipeline = container.voice_pipeline
    print(f"VoiceCommandPipeline has orchestrator: {pipeline._orchestrator is not None}")

    # Scenarios
    scenarios = [
        ("TEST 1: Git Project Report", "IRIS, check my GitHub repository and tell me what we've completed.", True),
        ("TEST 2: File Search", "IRIS, find my project report.", True),
        ("TEST 3: Browser Research", "IRIS, search the web for Python 3.14 release information and summarize it.", True),
        ("TEST 4: Safe Desktop Task", "IRIS, open Notepad and type hello.", True),
        ("TEST 5a: Legacy Command", "IRIS, open Chrome", False),
        ("TEST 5b: Agentic Follow-Up", "Tell me what files changed recently.", True),
        ("TEST 6: Confirmation Gate", "IRIS, delete file old_report.txt", True),
    ]

    print("\n--- 2. Live Voice Pipeline Tracing ---")
    results = []

    for name, utterance, expect_agent_core in scenarios:
        print(f"\nTracing: [{name}]")
        print(f"Utterance: '{utterance}'")

        # Parse intent
        parsed = container.intent_parser.parse(utterance)
        print(f"  -> IntentParser result: intent={parsed.intent.value}, target='{parsed.target}', query='{parsed.query}'")

        # Track if AgentCore process_goal is called
        agent_core_called = False
        original_process_goal = container.agent_core.process_goal

        def mock_process_goal(goal, context=None, skip_confirmation=False):
            nonlocal agent_core_called
            agent_core_called = True
            print(f"  *** AGENT CORE REACHED *** Goal: '{goal}'")
            return original_process_goal(goal, context, skip_confirmation)

        container.agent_core.process_goal = mock_process_goal

        # Process through live voice pipeline
        res = pipeline.execute(utterance)
        print(f"  -> Pipeline Result: success={res.success}, intent='{res.intent}', message='{res.message}'")
        print(f"  -> AgentCore Reached: {agent_core_called}")

        status = "PASS" if agent_core_called == expect_agent_core else "FAIL"
        results.append({
            "scenario": name,
            "agent_core_reached": agent_core_called,
            "parsed_intent": parsed.intent.value,
            "result_message": res.message,
            "status": status,
        })

        # Restore
        container.agent_core.process_goal = original_process_goal

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY AUDIT TABLE")
    print("=" * 80)
    print(f"{'Scenario':<30} | {'AgentCore Reached':<18} | {'Parsed Intent':<20} | {'Status'}")
    print("-" * 80)
    for r in results:
        reached = "YES" if r["agent_core_reached"] else "NO"
        print(f"{r['scenario']:<30} | {reached:<18} | {r['parsed_intent']:<20} | {r['status']}")


if __name__ == "__main__":
    audit_live_voice_pipeline()
