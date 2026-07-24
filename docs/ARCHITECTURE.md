# Architecture

## Overview
IRIS AI backend is a FastAPI server. The frontend is a React app running inside Electron.
They communicate over HTTP (`/api/*`) and WebSocket (planned).

## Module Ownership

| Module            | Owner  | Branch  |
|-------------------|--------|---------|
| eye_tracking      | Rehan  | rehan   |
| voice             | Prit   | prit    |
| automation        | Mehil  | mehil   |
| ai + database     | Meet   | dev     |
| frontend          | Meet   | dev     |

## Loose Coupling Strategy
- Each backend module exposes a clean class interface (no direct imports between modules).
- The API layer (`backend/api/routes/`) is the only place modules are wired together.
- Frontend talks to backend exclusively through `src/services/api.js`.
- Settings are injected via `backend/config/settings.py` — no hardcoded values anywhere.

## Branch Workflow
```
main ← develop ← feature branches (mehil, rehan, prit, dev)
```
- Never commit directly to `main` or `develop`.
- Open a PR from your feature branch → `develop`.
- `develop` → `main` for releases only.
