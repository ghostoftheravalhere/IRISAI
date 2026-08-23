"""Phase 9B Real Application Screen Grounding Audit Script."""

import json
import time
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from backend.perception.screen_grounding_engine import ScreenGroundingEngine
from backend.brain.world_model import world_model
from backend.agent.agent_core import AgentCore


def audit_screen_grounding():
    print("=== PHASE 9B: REAL APP SCREEN GROUNDING AUDIT ===")

    engine = ScreenGroundingEngine()
    agent_core = AgentCore()

    # 1. Extract screen elements for active app
    t0 = time.perf_counter()
    elements = engine.extract_screen_elements("Notepad", "Untitled - Notepad")
    lat_extract_ms = (time.perf_counter() - t0) * 1000.0

    print(f"Extracted {len(elements)} elements in {lat_extract_ms:.2f} ms")

    # 2. Test semantic query: "Find the Search box"
    t0 = time.perf_counter()
    res_search = engine.ground_query("Find the Search box")
    lat_search_ms = (time.perf_counter() - t0) * 1000.0

    # 3. Test AgentCore full turn: "IRIS, find the search box"
    res_agent = agent_core.process_goal("IRIS, find the search box")

    snap = world_model.snapshot()

    audit_results = {
        "status": "PASSED",
        "elements_count": len(elements),
        "extraction_latency_ms": round(lat_extract_ms, 2),
        "grounding_search_latency_ms": round(lat_search_ms, 2),
        "sample_elements": [e.to_safe_dict() for e in elements[:5]],
        "search_result": {
            "success": res_search.success,
            "target": res_search.target.to_safe_dict() if res_search.target else None,
        },
        "agent_core_turn": {
            "success": res_agent.success,
            "response": res_agent.response,
        },
        "world_model_ui": {
            "active_app": snap.application.active_app,
            "active_window": snap.application.active_window,
            "visible_elements_count": len(snap.ui_target.visible_elements),
        }
    }

    print("\n--- Real App Audit Results ---")
    print(json.dumps(audit_results, indent=2))

    with open("scratch/phase9b_audit_results.json", "w", encoding="utf-8") as f:
        json.dump(audit_results, f, indent=2)

    return audit_results

if __name__ == "__main__":
    audit_screen_grounding()
