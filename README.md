# IRIS AI
**Intelligent Responsive Interface System** — an AI-powered accessibility platform enabling hands-free computer control via webcam eye tracking, voice commands, desktop automation, and Gemini AI assistance.

## Windows Installer — V2.4 Submission

IRIS AI V2.4 is packaged as a **production-ready Windows Installer** for the IBM SkillsBuild Hackathon.

- **Standalone Installer**: [`IRIS-AI-V2.4-Setup.exe`](docs/INSTALLATION.md) (~256 MB)
- **Portable Executable**: `IRIS-AI-V2.4-Portable.exe` (~256 MB)
- **No Dependencies Required**: Bundled standalone Python 3.12 runtime, FastAPI backend, Faster-Whisper, MediaPipe, PyAutoGUI, and the offline `whisper-base` AI model. **0 Python/Node installation or terminal commands required by judges.**
- **Deployment Guide**: See [`docs/INSTALLATION.md`](docs/INSTALLATION.md) for full installation, launch, and uninstallation steps.

## Tech Stack
| Layer | Technology |
|---|---|
| Frontend | React 18 + Electron + Vite |
| Backend | Python + FastAPI |
| Computer Vision | OpenCV + MediaPipe |
| Speech | OpenAI Whisper |
| Automation | PyAutoGUI |
| AI | Google Gemini API |
| Database | SQLite + SQLAlchemy |

## Quick Start

**Windows:**
```bat
scripts\setup.bat
```

**macOS / Linux:**
```bash
bash scripts/setup.sh
```

**Run manually:**
```bash
# Terminal 1 — backend
cd backend && python main.py

# Terminal 2 — frontend
cd frontend && npm run dev
```

## Project Structure
```
IRISAI/
├── backend/
│   ├── eye_tracking/   # MediaPipe gaze detection (Rehan)
│   ├── voice/          # Whisper speech recognition (Prit)
│   ├── automation/     # PyAutoGUI desktop control (Mehil)
│   ├── ai/             # Gemini AI assistant (Meet)
│   ├── api/            # FastAPI server + routes
│   ├── database/       # SQLite models + sessions
│   ├── config/         # Environment settings
│   ├── utils/          # Shared helpers + logger
│   └── tests/          # pytest test suite
└── frontend/
    ├── electron/       # Main process + preload
    └── src/
        ├── components/ # Reusable UI components
        ├── pages/      # Route-level page components
        ├── hooks/      # Custom React hooks
        └── services/   # API client
```

## Branch Workflow
```
main ← develop ← mehil / rehan / prit / dev
```
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/FUTURE_SCOPE.md](docs/FUTURE_SCOPE.md) for full details.

## V2.4 Submission Scope Notice
Two-way conversational voice interaction with spoken IRIS responses is planned as a future enhancement. The current V2.4 submission intentionally uses voice input with visual response feedback (`VOICE_OUTPUT_ENABLED=False`) to maximize system stability and prevent audio feedback/self-hearing during demonstration.

## Environment
Copy `.env.example` to `.env` and fill in your `GEMINI_API_KEY`.
