"""
IRIS AI Backend Entry Point
Run from the repo root:  python -m backend.main
  or from backend/:      python main.py
"""
import sys
import os

if getattr(sys, "frozen", False):
    bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)
else:
    # Allow running as `python main.py` from inside backend/
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uvicorn
from backend.api.app import create_app
from backend.config.settings import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)
app = create_app()

if __name__ == "__main__":
    import os
    logger.info("[MAIN] Starting IRIS AI Backend in single-process mode (PID=%d)", os.getpid())
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,
        workers=1,
        log_level="debug" if settings.DEBUG else "info",
    )
