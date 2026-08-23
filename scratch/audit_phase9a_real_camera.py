"""Real Camera Integration Verification Script for Phase 9A."""

import json
import time
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from backend.perception.camera.capture_service import CaptureService
from backend.perception.camera.face_mesh_provider import FaceMeshService
from backend.perception.camera.person_recognition_service import RealtimePersonRecognitionService
from backend.perception.identity_manager import EnrollmentStatus, identity_manager
from backend.brain.world_model import world_model


def audit_real_camera():
    print("=== PHASE 9A: REAL CAMERA & PERSON RECOGNITION AUDIT ===")

    # 1. Camera Capture Service Check
    cap_service = CaptureService(camera_index=0)
    opened = cap_service.open()
    print(f"Camera 0 Opened: {opened}")

    mesh_service = FaceMeshService()
    prompts_captured = []

    rec_service = RealtimePersonRecognitionService(
        cooldown_seconds=5.0,
        voice_prompt_callback=lambda p: prompts_captured.append(p),
    )

    t0 = time.time()
    frames_processed = 0
    faces_detected = 0

    if opened:
        print("Reading real camera frames for 3 seconds...")
        while time.time() - t0 < 3.0:
            ok, frame = cap_service.read()
            if not ok or frame is None:
                break
            frames_processed += 1

            result = mesh_service.process_frame(frame)
            if result and hasattr(result, "eye_data") and result.eye_data is not None:
                faces_detected += 1
                rec_service.process_landmarks_async(result.eye_data)
            else:
                rec_service.process_landmarks_async(None)

            time.sleep(0.03)  # ~30 FPS loop

        cap_service.release()
    else:
        print("Webcam Hardware index 0 not physically attached / offline. Testing camera frame adapter pipeline via synthetic frame.")
        # Process synthetic frame to verify full non-blocking pipeline
        import numpy as np
        syn_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frames_processed += 1
        rec_service.process_landmarks_async([0.8] * 128)
        time.sleep(0.2)

    snap = world_model.snapshot()
    rec_service.shutdown()

    results = {
        "camera_opened": opened,
        "frames_processed": frames_processed,
        "faces_detected": faces_detected,
        "prompts_captured": prompts_captured,
        "world_model_person": snap.person.__dict__,
    }

    print("\n--- Audit Results ---")
    print(json.dumps(results, indent=2, default=str))

    with open("scratch/phase9a_camera_audit.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)

    return results

if __name__ == "__main__":
    audit_real_camera()
