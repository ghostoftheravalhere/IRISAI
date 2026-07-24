"""
IRIS AI Backend Entry Point
Run from the repo root:  python -m backend.main
  or from backend/:      python main.py
"""
import sys
import os

# Allow running as `python main.py` from inside backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uvicorn
from backend.api.app import create_app
from backend.config.settings import settings

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
