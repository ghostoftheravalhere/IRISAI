# IRIS AI V2.4 — Windows Installation & Demonstration Guide

**Intelligent Responsive Interface System**
*IBM SkillsBuild Hackathon Official Submission*

---

## Executive Overview

This guide is written specifically for **IBM SkillsBuild Hackathon judges, mentors, evaluators, and end-users** who wish to install, evaluate, and demonstrate **IRIS AI V2.4** on Windows.

**No separate Python or Node.js installation is required.**
**No npm commands are required.**
**No terminal commands are required.**

IRIS AI V2.4 is distributed as a **single, standalone, self-contained Windows Installer (`IRIS-AI-V2.4-Setup.exe`)** hosted on the official **GitHub Release (`v2.4.0`)**.

```
GitHub Releases (v2.4.0)
           │
           ▼
Download IRIS-AI-V2.4-Setup.exe (363.69 MB)
           │
           ▼
   Run Setup Installer Wizard
           │
           ▼
Launch IRIS AI Desktop Shortcut
           │
           ▼
 IRIS AI Interface Ready
```

---

## 1. Quick Judge Download & Installation Steps

Follow these 5 simple steps to install and run IRIS AI on any Windows PC:

1. **STEP 1**: Open the official GitHub Releases page:
   👉 **[IRIS AI V2.4 GitHub Release](https://github.com/ghostoftheravalhere/IRISAI/releases/tag/v2.4.0)**

2. **STEP 2**: Locate **"IRIS AI V2.4 — IBM SkillsBuild Submission"**.

3. **STEP 3**: In the **Assets** section at the bottom, click to download **`IRIS-AI-V2.4-Setup.exe`** (`363.69 MB`).

4. **STEP 4**: Run the downloaded **`IRIS-AI-V2.4-Setup.exe`** file.
   - *Security Note*: If Windows SmartScreen displays a warning (*"Windows protected your PC"*), click **More info** → **Run anyway**.
   - Click **Next** → **Install** → **Finish**.

5. **STEP 5**: Launch IRIS AI by double-clicking the **IRIS AI** Desktop shortcut (or Start Menu shortcut).
   - Allow camera and microphone permissions when prompted by Windows.
   - Electron starts automatically, connects to the bundled backend server, and presents the IRIS AI Dashboard in **READY** state.

---

## 2. System Requirements

The hardware and software specifications listed below reflect the actual IRIS AI V2.4 build:

| Component | Minimum Specification | Recommended Specification |
| :--- | :--- | :--- |
| **Operating System** | Windows 10 (64-bit) | Windows 11 (64-bit) |
| **Processor (CPU)** | Intel Core i3 / AMD Ryzen 3 (Dual-Core+) | Intel Core i5 / AMD Ryzen 5 (Quad-Core+) |
| **System Memory (RAM)**| 4 GB RAM | 8 GB RAM or higher |
| **Available Storage** | 1.2 GB free disk space | 2.0 GB free disk space |
| **Webcam** | Standard USB / Built-in 720p Webcam | 1080p HD Webcam (for eye tracking) |
| **Microphone** | Standard Built-in or USB Microphone | Noise-canceling USB Microphone |
| **Internet Connection**| **NONE (100% Offline Capability)** | None required |
| **Permissions** | User-level permissions (No Admin required) | Standard User account |

---

## 3. Installer Payload & Verification

- **Official Release Tag**: `v2.4.0`
- **Release Page URL**: `https://github.com/ghostoftheravalhere/IRISAI/releases/tag/v2.4.0`
- **Installer Direct Download**: `https://github.com/ghostoftheravalhere/IRISAI/releases/download/v2.4.0/IRIS-AI-V2.4-Setup.exe`
- **Verified File Size**: **363.69 MB** (`381,357,000+ bytes`)
- **SHA256 Checksum**: `9B52F78BA0D132353F905DAC9702169B86C7DF53FB8F8175E99BFFCF6ABE5F96`

### Bundled Components
The installer is completely self-contained and packages all required runtime components:

| Component | Bundled | Purpose in IRIS AI V2.4 |
| :--- | :---: | :--- |
| **Electron Application** | **Yes** | Cross-platform desktop application shell |
| **React Frontend** | **Yes** | Dashboard interface & real-time Command Log |
| **Standalone Python Runtime**| **Yes** | Embedded Python 3.12 environment (no manual Python install) |
| **FastAPI / Uvicorn** | **Yes** | Backend REST & WebSocket API server |
| **Faster-Whisper** | **Yes** | Local CTranslate2 speech recognition engine |
| **Whisper Base Model** | **Yes** | Offline AI model (`model.bin`, 138.49 MB included) |
| **MediaPipe** | **Yes** | Real-time facial landmark mesh & gaze tracking |
| **PyAutoGUI** | **Yes** | Windows desktop automation & cursor control |

---

## 4. First-Time Eye Gaze Calibration Guide

Perform these 10 simple steps to calibrate eye gaze tracking and test cursor control:

1. **Launch IRIS AI** from the Desktop shortcut.
2. Click **🎯 Calibrate Gaze** on the main dashboard action bar.
3. Position your face in front of the camera until face tracking displays **Detected**.
4. The calibration wizard displays **Point 1 / 9: Top-Left**.
5. Look directly at the pulsating target dot on the screen.
6. Click **Sample Point 1/9 →**.
7. Continue looking at each target dot (Top-Center, Top-Right, Middle-Left, Center, Middle-Right, Bottom-Left, Bottom-Center, Bottom-Right) and click **Sample Point**.
8. After Point 9 is sampled, observe the completion modal: **✓ Calibration Complete**.
9. Verify status displays **Cursor Control: READY**.
10. Click **▶ Start Cursor Control** → Status changes to **Cursor Control: ACTIVE**, and your eye gaze moves the screen cursor. Click **⏹ Stop Cursor Control** to pause movement.

---

## 5. Supported Voice Demonstration Commands

IRIS AI V2.4 utilizes a centralized `DesktopAppResolver` architecture with explicit application mappings. Test the following voice commands:

| Spoken Voice Command | Expected Behavior | Supported Resolution |
| :--- | :--- | :--- |
| `"Open Chrome"` | Google Chrome opens | Explicit `chrome.exe` registry lookup |
| `"Open Microsoft Edge"` | Microsoft Edge opens | Explicit `msedge.exe` lookup |
| `"Open Notepad"` | Windows Notepad opens | Explicit `notepad.exe` lookup |
| `"Open Microsoft Word"` | Microsoft Word opens | Explicit `Word 2016.lnk` Start Menu shortcut |
| `"Open Calculator"` | Windows Calculator opens | Explicit `calc.exe` system executable |
| `"Close IRIS"` | IRIS AI performs clean application exit | Graceful Electron & backend process teardown |

---

## 6. V2.4 Voice Output Configuration Notice

For the **IBM SkillsBuild Hackathon V2.4 Submission**, IRIS AI is intentionally operating in **Submission Stability Mode**:

- **Voice Input = ENABLED** (Microphone capture, Faster-Whisper offline transcription, intent parser, and desktop automation are 100% active).
- **Voice Output = DISABLED (Visual Feedback Only)** (IRIS responses display visually in the UI Dashboard and Command Log).

*Reasoning*: Disabling spoken audio output eliminates acoustic feedback and microphone self-hearing risks during live demonstration. Two-way spoken audio output is documented in `docs/FUTURE_SCOPE.md`.

---

## 7. Troubleshooting

### Camera Not Ready
- Ensure no other application (e.g., Zoom, Teams) is exclusively holding the webcam.
- Check Windows Privacy settings (**Settings** → **Privacy** → **Camera** = **ON**).
- Restart IRIS AI.

### Microphone Not Ready
- Ensure microphone privacy is enabled (**Settings** → **Privacy** → **Microphone** = **ON**).
- Ensure the microphone is connected and set as default input device.
- Click **🔄 Retry Microphone** on the dashboard.

### Cursor Control Not Moving
- Complete all 9 calibration points until **✓ Calibration Complete** appears.
- Verify status displays **Cursor Control: READY**.
- Click **▶ Start Cursor Control** to activate cursor tracking.

---

## 8. Submission Build Verification Summary

- **Automated Test Suite**: **74 / 74 PASSED (100% Green)** across 6 core test suites.
- **Frontend Production Build**: Vite bundle compiled cleanly in **1.77s**.
- **Windows Packaging**: NSIS installer packaged cleanly (**363.69 MB**).
- **Standalone Backend**: `iris_backend.exe` bundled and verified.
- **Offline Model**: Faster-Whisper base model (`model.bin`, 138.49 MB) included.
- **GitHub Release**: Tag `v2.4.0` live with attached `IRIS-AI-V2.4-Setup.exe`.
