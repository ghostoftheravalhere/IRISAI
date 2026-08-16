"""Phase 7E Real Multi-Service Jarvis Task Verification Script."""

import json
import time
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from backend.config.settings import Settings
from backend.core.di.container import build_container
from backend.agent.agent_core import AgentCore
from backend.agent.planner import Planner
from backend.agent.tools.email_tool import EmailTool
from backend.agent.tools.calendar_tool import CalendarTool
from backend.agent.tools.github_tool import GitHubTool


def audit_phase7e():
    print("=== PHASE 7E: REAL MULTI-SERVICE JARVIS TASK AUDIT ===")

    # Initialize live runtime container
    settings = Settings(APP_ENV="testing")
    container = build_container(settings)

    agent_core = container.agent_core
    voice_pipeline = container.voice_pipeline
    planner = Planner()

    available_tools = [EmailTool().descriptor, CalendarTool().descriptor, GitHubTool().descriptor]

    # --- 1. Measure Individual Tool & Planner Latencies ---
    print("\n--- 1. Measuring Component Latencies ---")
    
    t0 = time.perf_counter()
    plan = planner.create_plan("IRIS, check my email, calendar, and GitHub and tell me what needs my attention.", available_tools)
    t_planner = (time.perf_counter() - t0) * 1000
    print(f"Planner Latency: {t_planner:.2f} ms ({len(plan.steps)} steps)")

    # Execute EmailTool
    t0 = time.perf_counter()
    email_res = EmailTool().execute({"action": "get_pending_attention"})
    t_email = (time.perf_counter() - t0) * 1000
    print(f"EmailTool Latency: {t_email:.2f} ms | Success: {email_res.success}")

    # Execute CalendarTool
    t0 = time.perf_counter()
    cal_res = CalendarTool().execute({"action": "get_today_events"})
    t_cal = (time.perf_counter() - t0) * 1000
    print(f"CalendarTool Latency: {t_cal:.2f} ms | Success: {cal_res.success}")

    # Execute GitHubTool
    t0 = time.perf_counter()
    github_res = GitHubTool().execute({"action": "get_activity_summary"})
    t_github = (time.perf_counter() - t0) * 1000
    print(f"GitHubTool Latency: {t_github:.2f} ms | Success: {github_res.success}")

    # Measure Response Synthesis Latency
    t0 = time.perf_counter()
    synth_output = agent_core._synthesize_tool_results(
        "IRIS, check my email, calendar, and GitHub and tell me what needs my attention.",
        [
            ("email_tool", email_res),
            ("calendar_tool", cal_res),
            ("github_tool", github_res),
        ]
    )
    t_synth = (time.perf_counter() - t0) * 1000
    print(f"Synthesis Latency: {t_synth:.2f} ms")

    # --- 2. Live Full End-to-End Execution (Turn 1) ---
    print("\n--- 2. Live Full Agent Core Execution (Turn 1) ---")
    t0 = time.perf_counter()
    turn1_req = "IRIS, check my email, calendar, and GitHub and tell me what needs my attention."
    turn1_agent_res = agent_core.process_goal(turn1_req)
    t_e2e_turn1 = (time.perf_counter() - t0) * 1000

    print(f"Turn 1 Request: '{turn1_req}'")
    print(f"Turn 1 Response: '{turn1_agent_res.response}'")
    print(f"Turn 1 Total Latency: {t_e2e_turn1:.2f} ms")

    # --- 3. Multi-Turn Follow-Up (Turn 2) ---
    print("\n--- 3. Live Multi-Turn Follow-Up (Turn 2) ---")
    t0 = time.perf_counter()
    turn2_req = "What is the most important thing?"
    turn2_agent_res = agent_core.process_goal(turn2_req)
    t_e2e_turn2 = (time.perf_counter() - t0) * 1000

    print(f"Turn 2 Request: '{turn2_req}'")
    print(f"Turn 2 Response: '{turn2_agent_res.response}'")
    print(f"Turn 2 Total Latency: {t_e2e_turn2:.2f} ms")

    # --- 4. Multi-Turn Ambiguity Clarification (Turn 3) ---
    print("\n--- 4. Live Multi-Turn Ambiguity Clarification (Turn 3) ---")
    t0 = time.perf_counter()
    turn3_req = "Open it."
    turn3_agent_res = agent_core.process_goal(turn3_req)
    t_e2e_turn3 = (time.perf_counter() - t0) * 1000

    print(f"Turn 3 Request: '{turn3_req}'")
    print(f"Turn 3 Response: '{turn3_agent_res.response}'")
    print(f"Turn 3 Total Latency: {t_e2e_turn3:.2f} ms")

    results = {
        "latencies": {
            "planner_ms": round(t_planner, 2),
            "email_tool_ms": round(t_email, 2),
            "calendar_tool_ms": round(t_cal, 2),
            "github_tool_ms": round(t_github, 2),
            "synthesis_ms": round(t_synth, 2),
            "sequential_sum_tools_ms": round(t_email + t_cal + t_github, 2),
            "max_tool_ms": round(max(t_email, t_cal, t_github), 2),
            "potential_parallel_saving_ms": round((t_email + t_cal + t_github) - max(t_email, t_cal, t_github), 2),
            "turn1_total_e2e_ms": round(t_e2e_turn1, 2),
            "turn2_total_e2e_ms": round(t_e2e_turn2, 2),
            "turn3_total_e2e_ms": round(t_e2e_turn3, 2),
        },
        "turn1": {
            "request": turn1_req,
            "response": turn1_agent_res.response,
            "success": turn1_agent_res.success,
        },
        "turn2": {
            "request": turn2_req,
            "response": turn2_agent_res.response,
            "success": turn2_agent_res.success,
        },
        "turn3": {
            "request": turn3_req,
            "response": turn3_agent_res.response,
            "success": turn3_agent_res.success,
        },
        "email_data": email_res.data,
        "calendar_data": cal_res.data,
        "github_data": github_res.data,
    }

    # Write output to json
    with open("scratch/phase7e_audit_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    return results

if __name__ == "__main__":
    audit_phase7e()
