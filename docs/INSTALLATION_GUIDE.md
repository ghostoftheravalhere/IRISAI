# IRIS AI V2.4 — Windows Installation Guide

**Intelligent Responsive Interface System**
*IBM SkillsBuild Hackathon Official Submission*

---

## Executive Overview

This guide is designed for **IBM SkillsBuild Hackathon judges, mentors, evaluators, and end-users** who wish to install and run **IRIS AI V2.4** on Windows without setting up source code, installing Python, installing Node.js, running `npm` commands, or opening terminal windows.

IRIS AI V2.4 is distributed as a **single, production-ready, self-contained Windows Installer (`IRIS-AI-V2.4-Setup.exe`)**.

```
Download IRIS-AI-V2.4-Setup.exe
               │
               ▼
       Run Installer Wizard
               │
               ▼
  Launch IRIS AI Desktop Shortcut
               │
               ▼
     IRIS AI Interface Ready
```

---

## 1. System Requirements

The hardware and software requirements listed below are based on the actual IRIS AI V2.4 build:

| System Component | Minimum Requirement | Recommended Requirement |
| :--- | :--- | :--- |
| **Operating System** | Windows 10 (64-bit) | Windows 11 (64-bit) |
| **Processor (CPU)** | Intel Core i3 / AMD Ryzen 3 (Dual-Core) | Intel Core i5 / AMD Ryzen 5 (Quad-Core+) |
| **System Memory (RAM)**| 4 GB RAM | 8 GB RAM or higher |
| **Available Storage** | 1.2 GB free space | 2.0 GB free space |
| **Webcam** | 720p HD Webcam | 1080p HD Webcam (for optimal eye tracking) |
| **Microphone** | Standard Built-in or USB Microphone | Noise-canceling USB Microphone |
| **Internet Connection**| **NONE (100% Offline)** | None required |
| **Admin Privileges** | User-level permissions (No Admin required) | Standard User account |

---

## 2. Installer Overview

- **Installer Filename**: `IRIS-AI-V2.4-Setup.exe`
- **Installer File Size**: **363.69 MB** (approx. 364 MB)
- **Installer Type**: Standalone Windows NSIS Setup Executable

### Confirmed Packaged Components
The installer is completely self-contained and packages all runtime dependencies:

| Component | Bundled in Build | Purpose in IRIS AI V2.4 |
| :--- | :---: | :--- |
| **Electron Application** | **Yes** | Cross-platform desktop application shell |
| **React Frontend** | **Yes** | Interactive dashboard UI & command log display |
| **Standalone Python Runtime**| **Yes** | Embedded Python 3.12 environment (no manual Python install) |
| **FastAPI / Uvicorn** | **Yes** | Local REST & WebSocket API backend server |
| **Faster-Whisper** | **Yes** | High-performance CTranslate2 speech recognition engine |
| **Whisper Base Model** | **Yes** | Local offline AI model (`model.bin`, 145 MB included) |
| **MediaPipe** | **Yes** | Real-time facial landmark extraction & gaze tracking |
| **PyAutoGUI** | **Yes** | Windows desktop automation & cursor control |
| **SQLite / SQLAlchemy** | **Yes** | Local data persistent logging & preferences |

---

## 3. Installation Steps

Follow these simple steps to install IRIS AI on any Windows 10 or 11 computer:

### Step 1 — Download
Obtain the installer file from the official submission link:
`IRIS-AI-V2.4-Setup.exe`

### Step 2 — Start Installer
Double-click `IRIS-AI-V2.4-Setup.exe` to begin the installation wizard.
- *Security Note*: If Windows SmartScreen displays a warning (*"Windows protected your PC"*), click **More info** $\rightarrow$ **Run anyway**. This occurs because the submission executable is signed with a standard developer signature rather than a commercial EV certificate.

### Step 3 — Installation Wizard
The NSIS installation wizard will welcome you. Click **Next** to proceed.

### Step 4 — Installation Location
By default, IRIS AI installs to the user application folder:
`%LOCALAPPDATA%\Programs\IRIS AI` (e.g., `C:\Users\<User>\AppData\Local\Programs\IRIS AI`).
You can keep the default path or click **Browse** to select a different folder, then click **Install**.

### Step 5 — Shortcuts Created
The installer automatically creates:
- **Desktop Shortcut**: `IRIS AI`
- **Start Menu Shortcut**: `IRIS AI`
- **Windows Control Panel / App Settings Uninstaller**

### Step 6 — Finish & Launch
When installation completes, ensure **"Launch IRIS AI"** is checked and click **Finish**.

---

## 4. First Launch Experience

When IRIS AI launches from the desktop shortcut:

1. **Automatic Subprocess Management**: Electron launches `resources/backend/iris_backend.exe` automatically in the background.
2. **Health Check Polling**: Electron polls the local backend endpoint (`http://127.0.0.1:8000/health`) every 200ms until the backend confirms online status.
3. **Dashboard Presentation**: The React interface appears automatically with system status set to **READY**.

**Zero Terminal Commands Required**: Judges and evaluators do **NOT** need to open a terminal or manually run Python, FastAPI, Uvicorn, Node.js, or `npm`.

---

## 5. System Permissions Required

- **Webcam Access**: Requested on first launch to process MediaPipe gaze tracking and eye-blink detection.
- **Microphone Access**: Requested on first launch to record spoken commands for Faster-Whisper.
- **Desktop Automation**: Uses standard Windows accessibility hooks to execute application launching and window navigation. Administrator privileges are **NOT** required.

---

## 6. Verification Test for Evaluators

Perform this quick 2-minute test after installation to verify complete system functionality:

1. **Launch IRIS AI** from the Desktop shortcut.
2. **Verify Perception Cards**:
   - Camera Status: `Ready` (Webcam feed active)
   - Microphone Status: `Ready (On)`
   - Voice Input: `Active (Listening)`
3. **Test Command 1 (Chrome)**:
   - Say: `"Open Chrome"`
   - *Expected Result*: Google Chrome opens, and IRIS logs `Google Chrome opened.` in the Command Log.
4. **Test Command 2 (Calculator)**:
   - Say: `"Open Calculator"`
   - *Expected Result*: Windows Calculator opens, and IRIS logs `Windows Calculator opened.` in the Command Log.
5. **Test Command 3 (Microsoft Word)**:
   - Say: `"Open Microsoft Word"`
   - *Expected Result*: Microsoft Word opens if installed (`Word 2016.lnk`), or IRIS reports `Sir, I couldn't find Microsoft Word on this computer.` if Word is not installed. (*Word will NEVER open Microsoft Edge*).
6. **Test Command 4 (Self-Close)**:
   - Say: `"Close IRIS"`
   - *Expected Result*: IRIS logs `Closing IRIS, sir.` and performs a clean application exit, closing the frontend, backend, camera, and microphone streams.

---

## 7. V2.4 Voice Output Configuration Notice

For the **IBM SkillsBuild Hackathon V2.4 Submission**, IRIS AI is intentionally configured in **Submission Stability Mode**:

- **Voice Input = ENABLED** (Microphone capture, Faster-Whisper offline transcription, intent parser, and desktop automation are 100% active).
- **Voice Output = DISABLED (Visual Feedback Only)** (IRIS responses display visually in the UI Dashboard and Command Log).

*Note*: This visual feedback design decision eliminates audio feedback and self-hearing during demonstration. Two-way spoken audio output is documented in `docs/FUTURE_SCOPE.md`.

---

## 8. Application Features Available in Installed V2.4 Build

- **Voice Command Input**: Hands-free continuous microphone capture.
- **Faster-Whisper Speech Recognition**: Local offline transcription using the bundled `whisper-base` model.
- **Intent & Entity Parsing**: Verb-first intent parsing with strict application alias resolution.
- **Desktop Application Launching**: Centralized `DesktopAppResolver` launching system executables (`calc.exe`, `notepad.exe`), Start Menu shortcuts (`Word`, `Excel`, `PowerPoint`), and URI protocols (`ms-settings:`).
- **Webcam Eye Tracking**: MediaPipe 468-landmark facial mesh gaze tracking.
- **Gaze Cursor Movement**: Calibrated screen cursor movement driven by eye gaze.
- **Blink Gesture Detection**: Right and left eye blink detection for click triggering.
- **Visual Log Feedback**: Real-time System Diagnostics and Command Log history.
- **Clean Self-Shutdown**: Graceful exit via voice command (`"Close IRIS"`).

---

## 9. Troubleshooting Guide

### A. IRIS Does Not Start
- **Cause**: Port 8000 may be held by another application, or a previous IRIS process was not closed.
- **Solution**: Restart IRIS AI. If issues persist, check Task Manager and terminate any orphan process.

### B. Microphone Input Not Detected
- **Cause**: Windows Privacy settings blocking microphone access.
- **Solution**: Open **Windows Settings** $\rightarrow$ **Privacy & Security** $\rightarrow$ **Microphone**, and ensure *"Allow desktop apps to access your microphone"* is turned **ON**.

### C. Webcam / Eye Tracking Feed Dark or Inactive
- **Cause**: Webcam is in use by another application (e.g., Zoom, Teams).
- **Solution**: Close other camera apps and restart IRIS AI. Ensure camera privacy toggle is **ON** in Windows Settings.

### D. Application Phrase Reports "Could Not Be Found"
- **Cause**: Requested application (e.g., Microsoft Word) is not installed on the computer.
- **Solution**: IRIS cleanly reports: `Sir, I couldn't find <Application> on this computer.` This is expected behavior.

### E. Installer Fails to Launch
- **Cause**: Incomplete installer download.
- **Solution**: Verify `IRIS-AI-V2.4-Setup.exe` file size is approx. **363.69 MB**. Re-download if file size is incorrect.

---

## 10. Uninstallation Guide

To remove IRIS AI from your system:

### Option 1 — Windows Settings
1. Open **Windows Settings** (`Win + I`).
2. Go to **Apps** $\rightarrow$ **Installed apps** (or **Add/Remove Programs**).
3. Search for **IRIS AI**.
4. Click the three dots (`...`) next to IRIS AI and select **Uninstall**.

### Option 2 — Start Menu
1. Open the Windows **Start Menu**.
2. Locate **IRIS AI** $\rightarrow$ Click **Uninstall IRIS AI**.

---

## 11. Quick Demonstration Guide for IBM Judges

For evaluators conducting a live review of IRIS AI:

1. **Launch IRIS AI** from the Desktop shortcut (Wait ~3 seconds for backend auto-connect).
2. **View Dashboard**: Observe real-time Camera, Microphone, Eye Tracking, and System Diagnostics status.
3. **Voice Command Demo 1**: Say `"Open Chrome"` $\rightarrow$ Observe Chrome launch and UI log entry.
4. **Voice Command Demo 2**: Say `"Open Calculator"` $\rightarrow$ Observe Calculator launch and UI log entry.
5. **Voice Command Demo 3**: Say `"Open Settings"` $\rightarrow$ Observe Windows Settings launch via URI protocol.
6. **Eye Tracking Demo**: Move your eyes across the screen $\rightarrow$ Observe gaze coordinate tracking and cursor movement.
7. **Self-Close Demo**: Say `"Close IRIS"` $\rightarrow$ Observe clean application exit.

---

## 12. Offline & Internet Requirements

- **Internet Requirement**: **0% (100% Offline Capability)**.
- **Model Storage**: The 145 MB `whisper-base` model is pre-packaged inside the installer (`resources/models/whisper-base/model.bin`).
- **Data Privacy**: All speech recognition, eye tracking, and automation processing occur 100% locally on your computer. No audio recordings, video frames, or user data are transmitted over the internet.

---

## 13. Version & Build Information

- **Application Name**: IRIS AI (Intelligent Responsive Interface System)
- **Application Version**: V2.4 (SkillsBuild Submission Build)
- **Installer File**: `IRIS-AI-V2.4-Setup.exe` (363.69 MB)
- **Portable File**: `IRIS-AI-V2.4-Portable.exe` (363.69 MB)
- **Target Platform**: Windows 10 / 11 (64-bit)
- **Hackathon Event**: IBM SkillsBuild Hackathon
