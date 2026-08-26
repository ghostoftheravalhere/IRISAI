# IRIS AI
**Intelligent Responsive Interface System** — an AI-powered accessibility platform enabling hands-free computer control via webcam eye tracking, voice commands, desktop automation, and Gemini AI assistance.

## Quick Start — IBM Submission

Download the ready-to-run Windows installer from the official **[IRIS AI V2.4 GitHub Release](https://github.com/ghostoftheravalhere/IRISAI/releases/tag/v2.4.0)**.

- **Standalone Installer Download**: [IRIS-AI-V2.4-Setup.exe](https://github.com/ghostoftheravalhere/IRISAI/releases/download/v2.4.0/IRIS-AI-V2.4-Setup.exe) (**363.69 MB**)
- **Official GitHub Release Tag**: [`v2.4.0`](https://github.com/ghostoftheravalhere/IRISAI/releases/tag/v2.4.0)
- **SHA256 Checksum**: `1C471642EC224AA691FDD79CBBFF0A04A43FC74F207835500A3DDD6D3564FE5D`
- **Zero Dependencies Required**: Bundled standalone Python 3.12 runtime, FastAPI backend, Faster-Whisper, MediaPipe, PyAutoGUI, and the offline `whisper-base` AI model. **0 Python/Node.js installation or terminal commands required by judges.**
- **Judge Demonstration Guide**: See [`docs/INSTALLATION_GUIDE.md`](docs/INSTALLATION_GUIDE.md) for step-by-step installation, eye-gaze calibration, voice commands, and troubleshooting.

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
