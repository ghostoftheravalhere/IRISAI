# IRIS AI V2.4 — Installation & Deployment Guide

Welcome to **IRIS AI** (Intelligent Responsive Interface System), a multi-modal desktop assistant built for the **IBM SkillsBuild Hackathon**.

This guide outlines how to install, launch, and use the standalone IRIS AI V2.4 application on Windows without requiring pre-installed developer dependencies (such as Python, Node.js, npm packages, or terminal commands).

---

## 1. System Requirements

- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **Memory (RAM)**: 4 GB minimum (8 GB recommended)
- **Disk Space**: ~1.2 GB free space after installation
- **Hardware Peripherals**:
  - Standard USB/Built-in Webcam (for gaze tracking & eye-blink detection)
  - Standard Microphone (for continuous voice recognition)

---

## 2. Installation Package Summary

| Artifact Name | Type | Size | Description |
| :--- | :--- | :--- | :--- |
| **`IRIS-AI-V2.4-Setup.exe`** | NSIS Installer | **~256 MB** | Production Windows Installer creating Desktop & Start Menu shortcuts + Uninstaller |
| **`IRIS-AI-V2.4-Portable.exe`** | Portable Binary | **~256 MB** | Self-contained single executable running directly without system installation |

### Bundled AI & Runtime Components

- **Python Backend**: Self-contained PyInstaller executable (`iris_backend.exe`) bundled with Python 3.12 runtime.
- **Speech-to-Text Model**: Offline Faster-Whisper base model (`resources/models/whisper-base/model.bin`, 145 MB). **100% Offline — No HuggingFace download or internet required.**
- **Perception & Automation**: OpenCV, MediaPipe, SoundDevice, PyAutoGUI, FastAPI, Uvicorn, SQLite.
- **Frontend Interface**: Electron 31 + React 18 production distribution bundle.

---

## 3. Installation Steps (Judge / End-User Walkthrough)

### Step 1: Download & Run Installer
1. Download **`IRIS-AI-V2.4-Setup.exe`**.
2. Double-click **`IRIS-AI-V2.4-Setup.exe`** to launch the installer wizard.

### Step 2: Choose Install Directory
1. The installer defaults to standard user application path (`%LOCALAPPDATA%\Programs\IRIS AI`).
2. Click **Install**.

### Step 3: Desktop & Start Menu Shortcuts
- The installer automatically creates:
  - **Desktop Shortcut**: `IRIS AI`
  - **Start Menu Shortcut**: `IRIS AI`

### Step 4: Launching IRIS AI
1. Check **Launch IRIS AI** and click **Finish** (or launch from Desktop shortcut).
2. Electron starts automatically and initializes the bundled Python backend executable.
3. The system performs an automatic 200ms health check loop until `/health` returns online status.
4. The IRIS AI Runtime Dashboard appears as **READY**.

---

## 4. First-Launch & Runtime Overview

1. **Camera & Eye Tracking**: IRIS initializes your webcam for MediaPipe gaze tracking and blink gesture detection.
2. **Microphone & Voice Input**: Microphone status displays `Active (Listening)`. Spoken user commands (`"Open Chrome"`, `"Open Microsoft Word"`, `"Open Calculator"`) appear in the Command Log.
3. **Visual Response Feedback**: In V2.4 Submission Mode, IRIS presents responses visually in the UI and Command Log (`VOICE_OUTPUT_ENABLED = False`) to maximize stability during live hackathon demonstration.
4. **Closing IRIS**:
   - Speak `"Close IRIS"`, `"Exit IRIS"`, `"Quit IRIS"`, or `"Close yourself"`.
   - IRIS logs `Closing IRIS, sir.` and executes graceful process teardown, stopping the backend, camera, microphone, and socket ports cleanly with **0 orphaned processes**.

---

## 5. How to Uninstall IRIS AI

1. Open **Windows Settings** $\rightarrow$ **Apps** $\rightarrow$ **Installed Apps** (or **Add/Remove Programs**).
2. Search for **IRIS AI**.
3. Click **Uninstall** and follow the prompts.

---

## 6. Troubleshooting & Diagnostics

If the backend does not start or a port conflict occurs:
- **Port Conflict**: IRIS backend uses port `8000`. Ensure no other application is holding port `8000`.
- **Diagnostic Logs**: Application runtime logs are saved to `%APPDATA%\IRIS AI\logs\`.
