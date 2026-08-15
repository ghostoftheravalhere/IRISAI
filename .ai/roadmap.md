# IRIS AI V4 — Product Roadmap

## Completed Milestones

1. **Core Contracts & Configuration**
   - Centralized `Settings` with environment variable overrides (`pydantic-settings`).
   - Logging, domain exceptions, and base models.

2. **Dependency Injection Extraction**
   - Modular application container (`AppContainer`) pattern (`backend/core/di/container.py`).

3. **Perception Layer Modernization**
   - Event bus architecture for inter-module communication.
   - Structured perception event models (`PerceptionEvent`).

4. **Voice Pipeline Stabilization**
   - Push-to-talk (PTT) audio buffer capture and preprocessing.
   - Fast offline transcription using Faster-Whisper (`base.en`).

5. **Eye-Tracking & Gaze Dataset Infrastructure**
   - MediaPipe face mesh eye center tracking and EAR blink detection.
   - 9-point screen calibration engine and polynomial gaze mapping.

6. **Multimodal Gaze + Voice Fusion**
   - Temporal correlation window and rule-based fusion (`DeicticSpatialFusionRule`, `GazeVoiceFusionRule`).

7. **Calibration Guidance System**
   - Real-time calibration status reporting and validation thresholds.

8. **FastAPI Lifespan Modernization**
   - Lifespan context manager in `api/app.py` for service startup/shutdown.

9. **Electron Backend Auto-Start**
   - Electron `BackendManager` detecting dev Python vs. packaged backend executable.

10. **Backend Readiness UI**
    - Dynamic connection status indicator and readiness polling in React UI.

11. **Graceful Electron Teardown**
    - Signal handling (SIGINT/SIGTERM) and tree-kill process cleanup on Electron app close.

12. **PyInstaller Backend Packaging (Phase 4.1)**
    - Standalone `--onedir` bundle generation (`iris_backend.exe`) via `iris_backend.spec`.

13. **Offline Whisper Model Packaging (Phase 4.2)**
    - Bundled Faster-Whisper `base.en` model assets into local backend distribution directory.

14. **Electron Production Backend Integration (Phase 4.3)**
    - Electron production resolution loading `resources/backend/iris_backend.exe`.

15. **NSIS Windows Installer Packaging (Phase 4.4)**
    - Self-contained installer `IRIS.AI.Setup.4.0.0.exe` via `electron-builder`.

16. **Conversational Accessibility Agent**
    - Jarvis-style natural language interaction (`ActionEngine`, `AmbiguityEngine`, `DialogueManager`, `SelectionManager`).

---

## Future Roadmap Milestones

1. **Gaze Dataset Acquisition**
   - Real-world multi-user gaze data collection across varied lighting and head poses.

2. **Gaze Deep Learning Training**
   - Model training (CNN/ResNet gaze estimator) replacing polynomial calibration fallback.

3. **Gaze ML Runtime Integration**
   - Low-latency ONNX / PyTorch runtime deployment into backend eye-tracking pipeline.

4. **Advanced Conversational Capabilities**
   - Screen visual understanding integration (OCR + UIA hybrid layout analysis for complex apps).

5. **Code-Signing & Auto-Updater**
   - EV certificate code-signing for Windows binaries and Electron auto-updater integration.
