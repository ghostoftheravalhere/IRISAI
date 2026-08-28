# IRIS AI — Release Notes & Architecture Changelog

---

## Release v2.4.5 (Production-Ready Multimodal Gaze-Voice Fusion & Win32 OS Engine)
**Release Date:** August 28, 2026  
**Target Platform:** Windows 10 / Windows 11 (x64)  
**Binary Artifact:** `IRIS-AI-Setup-v2.4.5.exe` (Standalone Electron NSIS Production Installer)

---

### Executive Overview

IRIS AI v2.4.5 delivers a major leap in multimodal hands-free human-computer interaction, combining state-of-the-art computer vision gaze estimation, local offline Whisper ASR voice command dispatching, and native Win32 operating system automation.

This release addresses critical physical interaction challenges, including blink-induced pupil drift, DPI-scaling coordinate misalignments, microphone initialization contention, and seamless gaze-voice fusion with universal fallback.

---

### Key Architectural Improvements in v2.4.5

#### 1. Native Win32 OS Cursor Engine
- **Direct Windows API Invocation**: Replaced high-latency third-party pointer dispatchers with direct `ctypes.windll.user32` calls:
  - `SetCursorPos(clamped_x, clamped_y)` for absolute hardware cursor placement.
  - `mouse_event(dwFlags, 0, 0, 0, 0)` with zeroed relative displacement for click, double-click, drag, and drop events.
- **Per-Monitor DPI Awareness (Level 2)**: Calls `SetProcessDpiAwareness(2)` on initialization to guarantee accurate coordinate alignment across 100%, 125%, 150%, and 200% display scaling factors.
- **Strict Coordinate Clamping**: Automatically resolves physical screen boundaries via `GetSystemMetrics(0)` (width) and `GetSystemMetrics(1)` (height), ensuring cursor coordinates are clamped safely to `[0, screen_w - 1]` and `[0, screen_h - 1]`.
- **50ms Double-Click Cadence**: Implements a calibrated 50ms interval between click cycles to guarantee OS message queue recognition for native application double-clicks.

#### 2. Pre-Blink Time Machine & EAR Freeze Gate (`EAR_FREEZE_THRESHOLD = 0.31`)
- **Blink Drift Elimination**: During intentional single/double blinks, natural eyelid closure drags the estimated pupil center downwards. To prevent cursor drop:
  - Tuned `EAR_FREEZE_THRESHOLD = 0.31` in `EyeTrackingConfig` to detect the onset of blink closure earlier in the frame cycle.
  - Guarded coordinate buffer so that as soon as `current_ear < 0.31`, the 30-frame rolling coordinate buffer halts ingestion of distorted coordinates.
- **Retroactive Time Machine Dispatch**: On confirmed blink clicks, coordinates are retrieved from the pre-blink window, ensuring 100% target accuracy on small UI elements (buttons, menu items, checkboxes).

#### 3. Multimodal Gaze-Voice Fusion Engine
- **Synchronous Gaze-Voice Anchoring**: When speech onset is detected (via local Whisper VAD or Push-to-Talk activation), the engine locks the user's current gaze coordinates as a `GazeAnchor`.
- **Punctuation-Agnostic & Case-Insensitive Matching**: Voice commands (`"click"`, `"right click"`, `"double click"`, `"open"`, `"drag"`, `"drop"`) sanitize punctuation (`!`, `.`, `?`, `,`) and match intents with zero latency.
- **Universal Physical Cursor Fallback (`force=True`)**:
  - If gaze cursor control is toggled OFF, or if gaze tracking is temporarily occluded, voice actions gracefully fall back to the physical system cursor position (`system_cursor.get_cursor_position()`).
  - Passes `force=True` to execute OS actions universally whether eye tracking is active or idle.
- **Direct "Open" Gesture**: Uttering `"open"` or `"double click"` immediately executes a native double left-click at the fixation target.

#### 4. Fullscreen 9-Point Calibration
- **Edge-to-Edge Screen Mapping**: Integrated Electron IPC handlers (`window:set-fullscreen` and `window:maximize`) triggered automatically upon starting calibration.
- **1:1 Display Edge Mapping**: Maximizing the calibration viewport allows 9-point regression targets (especially corner and bottom points such as Point 7) to align with the true physical edges of the display.

#### 5. Bulletproof Microphone & Audio Stream Initialization
- **500ms Pre-Warm Settling Delay**: Added a non-blocking pre-warm settling delay prior to opening `sounddevice.InputStream` to eliminate Windows PortAudio endpoint lock contention.
- **PortAudio Error Recovery**: Catches `sd.PortAudioError` and device acquisition delays, cleanly resetting the stream and falling back to `device=None` (system default input) so the first voice recognition attempt never fails with "Microphone unavailable".

#### 6. Unified Developer Workflow & Standalone Bundling
- **Single-Command Development**: `npm run dev` concurrently orchestrates Electron, Vite React frontend, and the Python FastAPI/Uvicorn backend.
- **Electron-Builder Production Bundling**:
  - `electron-builder.yml` packages the full Python backend and `.venv` virtual environment into `resources/backend`.
  - `backendManager.js` dynamically routes between development virtualenv paths and packaged `process.resourcesPath` environments.
  - Builds standalone NSIS installer: `IRIS-AI-Setup-v2.4.5.exe`.

---

### Test Suite & Verification Results

- **Backend PyTest Regression Suite**: **123 / 123 Tests Passed (100% Green)**
  - `backend/tests/test_gaze_voice_fusion.py`: 33 passed
  - `backend/tests/test_system_cursor.py`: 9 passed
  - `backend/tests/test_blink_freeze_buffer.py`: 4 passed
  - `backend/tests/test_voice.py`: 13 passed
  - `backend/tests/test_eye_tracking.py`: 9 passed
  - `backend/tests/test_voice_cursor_control.py`: 44 passed
  - `backend/tests/test_fusion_engine.py`: 11 passed
- **Frontend Build**: Vite + Electron compilation clean (`dist/` generated with 0 errors).

---

### Version History Summary

| Version | Release Highlights |
|---|---|
| **v2.4.5** | Native Win32 OS Cursor Engine, Pre-Blink EAR Freeze (0.31), Multimodal Gaze-Voice Fusion, Fullscreen Calibration, Bulletproof Audio Pre-Warm, Standalone NSIS Installer. |
| **v2.4.4** | Universal application resolution (Edge, Notepad, Chrome, Office), Process Tree PID tracking, PTT RMS noise gating. |
| **v2.4.2** | MediaPipe FaceMesh eye gaze estimation pipeline, 9-point polynomial calibration, Electron desktop shell. |
| **v2.0.0** | Initial modular architecture transition to FastAPI backend + React Vite frontend. |
