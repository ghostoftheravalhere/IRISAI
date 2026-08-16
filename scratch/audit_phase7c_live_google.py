"""Phase 7C Real Google Data Verification Script."""

import json
import time
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from backend.auth.google_auth_service import google_auth_service
from backend.agent.tools.email_tool import EmailTool
from backend.agent.tools.calendar_tool import CalendarTool
from backend.brain.orchestrator import BrainOrchestrator
from backend.agent.agent_core import AgentCore
from backend.voice.command_parser import IntentParserService
from backend.agent.task_state import TaskState
from backend.agent.response_generator import ResponseGenerator

def audit_phase7c():
    results = {}

    print("=== 1. ACCOUNT STATUS ===")
    t0 = time.perf_counter()
    status_str = google_auth_service.get_status()
    email = google_auth_service.get_account_email()
    t_status = (time.perf_counter() - t0) * 1000

    results["account_status"] = {
        "status": status_str,
        "is_connected": status_str == "Google connected",
        "account_email": email,
        "latency_ms": round(t_status, 2),
    }
    print(f"Status: {status_str} | Email: {email} | Latency: {t_status:.2f}ms")

    print("\n=== 2. REAL GMAIL TEST ===")
    email_tool = EmailTool()
    
    # Query 1: Unread count
    t0 = time.perf_counter()
    res1 = email_tool.execute({"action": "get_unread_count"})
    t1 = (time.perf_counter() - t0) * 1000
    
    # Query 2: Pending emails
    t0 = time.perf_counter()
    res2 = email_tool.execute({"action": "get_pending_attention"})
    t2 = (time.perf_counter() - t0) * 1000

    # Query 3: Important / Latest unread
    t0 = time.perf_counter()
    res3 = email_tool.execute({"action": "get_important_unread", "limit": 1})
    t3 = (time.perf_counter() - t0) * 1000

    results["gmail"] = {
        "unread_count_query": {"success": res1.success, "data": res1.data, "message": res1.message, "latency_ms": round(t1, 2)},
        "pending_query": {"success": res2.success, "data": res2.data, "message": res2.message, "latency_ms": round(t2, 2)},
        "latest_unread_query": {"success": res3.success, "data": res3.data, "message": res3.message, "latency_ms": round(t3, 2)},
    }
    print("Gmail Unread:", res1.data, f"({t1:.2f}ms)")
    print("Gmail Pending:", res2.data, f"({t2:.2f}ms)")
    print("Gmail Latest:", res3.data, f"({t3:.2f}ms)")

    print("\n=== 3. REAL CALENDAR TEST ===")
    cal_tool = CalendarTool()

    # Query 1: Today events
    t0 = time.perf_counter()
    c_res1 = cal_tool.execute({"action": "get_today_events"})
    ct1 = (time.perf_counter() - t0) * 1000

    # Query 2: Next event
    t0 = time.perf_counter()
    c_res2 = cal_tool.execute({"action": "get_next_event"})
    ct2 = (time.perf_counter() - t0) * 1000

    # Query 3: Tomorrow events
    t0 = time.perf_counter()
    c_res3 = cal_tool.execute({"action": "get_events_by_date", "date": "tomorrow"})
    ct3 = (time.perf_counter() - t0) * 1000

    results["calendar"] = {
        "today_query": {"success": c_res1.success, "data": c_res1.data, "message": c_res1.message, "latency_ms": round(ct1, 2)},
        "next_event_query": {"success": c_res2.success, "data": c_res2.data, "message": c_res2.message, "latency_ms": round(ct2, 2)},
        "tomorrow_query": {"success": c_res3.success, "data": c_res3.data, "message": c_res3.message, "latency_ms": round(ct3, 2)},
    }
    print("Calendar Today:", c_res1.data, f"({ct1:.2f}ms)")
    print("Calendar Next Event:", c_res2.data, f"({ct2:.2f}ms)")
    print("Calendar Tomorrow:", c_res3.data, f"({ct3:.2f}ms)")

    print("\n=== 4. VOICE PIPELINE AUDIT ===")
    orchestrator = BrainOrchestrator()
    
    voice_phrases = [
        "IRIS, do I have any unread emails?",
        "IRIS, what meetings do I have today?",
        "IRIS, what is my next event?",
    ]
    
    voice_results = []
    for phrase in voice_phrases:
        t0 = time.perf_counter()
        orchestrator_resp = orchestrator.process_user_request(phrase)
        v_lat = (time.perf_counter() - t0) * 1000
        voice_results.append({
            "input_phrase": phrase,
            "success": orchestrator_resp.get("success", False),
            "response": orchestrator_resp.get("response", ""),
            "latency_ms": round(v_lat, 2),
        })
        print(f"Voice Phrase: '{phrase}' -> Response: '{orchestrator_resp.get('response')}' ({v_lat:.2f}ms)")

    results["voice_pipeline"] = voice_results

    # Write output to json scratch file
    with open("scratch/phase7c_audit_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    return results

if __name__ == "__main__":
    audit_phase7c()
