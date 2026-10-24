# IRIS AI — Intelligent Responsive Interface System

[![Release](https://img.shields.io/badge/Release-v2.5.0-blue.svg)](https://github.com/ghostoftheravalhere/IRISAI/releases/tag/v2.5.0)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011%20(x64)-brightgreen.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)]()
[![Electron](https://img.shields.io/badge/Electron-31.0.0-informational.svg)]()

**IRIS AI** is an AI-powered desktop accessibility system engineered to provide **fully hands-free computer control**. By uniting real-time webcam eye tracking, intentional blink gesture recognition, local offline Whisper speech-to-text, and native Win32 operating system automation, IRIS AI empowers individuals with motor disabilities, quadriplegia, ALS, cerebral palsy, or severe repetitive strain injuries (RSI) to interact seamlessly with their computers without touching a keyboard or mouse.

---

## What's New in v2.5.0

IRIS AI v2.5.0 is our most reliable and precise accessibility release to date:

* **Fullscreen 16-Point Precision Calibration**: Upgraded from legacy 9-point calibration to a comprehensive 4x4 coordinate matrix (16 points) spanning 10% to 90% of screen dimensions to dramatically improve edge and corner gaze tracking.
* **4-Target Independent Held-Out Validation**: Evaluates gaze accuracy against four dedicated validation targets not included during polynomial fitting, providing an objective mathematical verification of calibration quality.
* **Strict Cursor Safety Authorization Gating**: Gaze-controlled cursor output remains strictly disabled (`is_authorized = false`) until calibration passes quality and validation thresholds, preventing unpredictable pointer jumps.
* **Draggable Floating Calibration Panel**: Replaced static full-screen blocking modals with a draggable floating HUD that automatically dodges active gaze targets to eliminate visual occlusion.
* **Full-System Voice Dictation & OS Navigation**: Dictate text directly into arbitrary Windows applications (Notepad, Word, browsers, chat tools) and control window states (*"scroll down"*, *"open chrome"*, *"close window"*, *"switch window"*).
* **Graceful HTTP Shutdown & Process Tree Teardown**: Eliminates orphaned background processes and port 8000 socket collisions by coordinating clean HTTP shutdown (`POST /api/v1/shutdown`), camera/mic release, and targeted fallback process termination.
* **100% Offline AI Execution**: Faster-Whisper INT8 models and MediaPipe computer vision run locally on your device with zero cloud latency and no internet connection required.

For comprehensive architectural details and commit history, see [`RELEASE_NOTES_v2.5.0.md`](RELEASE_NOTES_v2.5.0.md).

---

## Major Capabilities

1. **Gaze Pointer Control**: Real-time facial landmark estimation via MediaPipe FaceMesh, computing normalized eye centers and mapping them to absolute screen coordinates using polynomial calibration curves and kinematic physics smoothing.
2. **Intentional Blink Detection**: Continuous Eye Aspect Ratio (EAR) temporal tracking that distinguishes natural physiological blinks (100–300 ms) from intentional command blinks (400–1200 ms) to trigger left clicks, right clicks, and double clicks.
3. **Blink Freeze Stabilization**: Locks the cursor position the instant a blink begins, neutralizing the downward cursor drift that typically occurs as eyelids close over the pupil.
4. **Local Voice Command Engine**: Offline speech recognition powered by Faster-Whisper, enabling hands-free system navigation, browser launching, scrolling, and application switching.
5. **Universal Desktop Dictation**: Direct text entry injected via native Win32 `SendInput` APIs, supporting real-time dictation across any active Windows application.
6. **Gemini AI Multimodal Assistant**: Optional conversational AI assistant integration for desktop summarization, contextual guidance, and intelligent workflow acceleration.

---

## Supported Platform & Prerequisites

* **Operating System**: Windows 10 or Windows 11 (64-bit AMD64).
* **Hardware Requirements**:
  * Standard USB or built-in webcam (720p or 1080p recommended).
  * Built-in or USB microphone.
  * Minimum 4 GB RAM (8 GB recommended for optimal Whisper performance).
* **Environment**:
  * Balanced frontal lighting (avoid strong backlighting or direct sunlight).
  * Centered webcam placement facing the user.

---

## Quick Start (Pre-built Windows Installer)

For everyday users and clinical evaluation, download the official self-contained installer:

1. Download [`IRIS-AI-v2.5.0-Setup.exe`](https://github.com/ghostoftheravalhere/IRISAI/releases/download/v2.5.0/IRIS-AI-v2.5.0-Setup.exe) from the [Official GitHub Release](https://github.com/ghostoftheravalhere/IRISAI/releases/tag/v2.5.0).
2. Run the installer. If Windows SmartScreen displays *"Windows protected your PC"* (due to the application being unsigned):
   * Click **More info**.
   * Click **Run anyway**.
3. Follow the installation wizard.
4. Launch **IRIS AI** from your Desktop or Start Menu.
5. On first launch, navigate to the **Calibration** tab and complete the 16-point gaze calibration wizard.

---

## Running from Source (Developer Setup)

### 1. Prerequisites
* **Python**: 3.11 or 3.12 (64-bit)
* **Node.js**: 18.x or 20.x
* **Git**: Installed and available in your PATH

### 2. Clone Repository
```bash
git clone https://github.com/ghostoftheravalhere/IRISAI.git
cd IRISAI
```

### 3. Backend Setup
```bash
# Create and activate Python virtual environment
python -m venv backend/.venv

# Windows (PowerShell):
backend\.venv\Scripts\Activate.ps1
# Windows (CMD):
backend\.venv\Scripts\activate.bat

# Install backend dependencies
pip install -r backend/requirements.txt
```

### 4. Frontend Setup
```bash
cd frontend
npm install
cd ..
```

### 5. Running the Application in Development Mode
You can start the full stack (FastAPI backend + Vite dev server + Electron runtime) with a single command from `frontend/`:
```bash
cd frontend
npm run dev
```

Alternatively, run each tier in separate terminals:
```bash
# Terminal 1 — Backend API (from repo root)
backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — Frontend UI & Electron (from frontend/)
cd frontend
npm run dev:vite
npm run electron
```

---

## Optional Configuration & API Keys

Core eye-tracking, blink clicks, and offline Whisper voice dictation function **100% locally with zero API keys**.

To enable optional Google Gemini AI assistant features:
1. Copy `.env.example` to `.env` in the repository root:
   ```bash
   copy .env.example .env
   ```
2. Configure your keys:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

---

## Running Tests

### Backend Test Suite
Run unit tests, calibration verification, and lifecycle shutdown checks:
```bash
# Run 16-point calibration verification
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_gaze_calibration_16point.py -v

# Run graceful shutdown & lifecycle verification
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_graceful_shutdown.py -v

# Run eye cursor safety & API tests
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_eye_cursor_api.py -v

# Run full backend test suite
backend\.venv\Scripts\python.exe -m pytest backend/tests/ -v
```

### Frontend Test Suite
Run coordinate mapping and UI wizard tests:
```bash
cd frontend
npm test
```

---

## Packaging the Production Installer

To produce the standalone Windows installer from source:
```bash
cd frontend
# 1. Build frontend bundle
npm run build:vite

# 2. Compile standalone Python backend executable
npm run build:backend

# 3. Package Electron installer
npx electron-builder --win --x64
```
The resulting installer will be output to [`release/IRIS-AI-v2.5.0-Setup.exe`](release/IRIS-AI-v2.5.0-Setup.exe).

---

## Current Limitations

* **Lighting Conditions**: MediaPipe face mesh landmarks require consistent ambient room lighting. Extreme backlighting, darkness, or intense directional glare can cause landmark jitter.
* **Webcam Angle**: Optimal accuracy requires the webcam to be positioned near eye level (directly above or below the primary display).
* **Eyeglasses & Reflections**: Thick-rimmed frames or heavy anti-reflective lens glare can intermittently distort Eye Aspect Ratio (EAR) calculations.
* **Multi-Monitor Coordinate Offsets**: Primary monitor gaze calibration operates within the calibrated display viewport. Virtual desktop panning across disparate DPI monitors is in active development.

---

## Reporting Issues & Contributing

If you encounter a bug, drift issue, or accessibility barrier:
* Open an issue on our [GitHub Issue Tracker](https://github.com/ghostoftheravalhere/IRISAI/issues).
* Include details about your webcam model, display resolution, and Windows version.
* Check [`backend/logs/`] or the Electron console for diagnostic traces.

---

## License

IRIS AI is released under the [MIT License](LICENSE).
