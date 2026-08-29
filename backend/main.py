"""
IRIS AI Backend Entry Point
Run from the repo root:  python -m backend.main
  or from backend/:      python main.py
"""
import sys
import io
import os

if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

if getattr(sys, "frozen", False):
    bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)
    try:
        import api
        import agent
        import automation
        import brain
        import config
        import core
        import eye_tracking
        import perception
        import utils
        import voice
        import types
        sys.modules["backend"] = types.ModuleType("backend")
        sys.modules["backend.api"] = api
        sys.modules["backend.agent"] = agent
        sys.modules["backend.automation"] = automation
        sys.modules["backend.brain"] = brain
        sys.modules["backend.config"] = config
        sys.modules["backend.core"] = core
        sys.modules["backend.eye_tracking"] = eye_tracking
        sys.modules["backend.perception"] = perception
        sys.modules["backend.utils"] = utils
        sys.modules["backend.voice"] = voice
    except Exception as e:
        pass
else:
    # Allow running as `python main.py` from inside backend/ or from workspace root
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

import uvicorn
try:
    from backend.api.app import create_app
    from backend.config.settings import settings
    from backend.utils.logger import get_logger
except ModuleNotFoundError:
    from api.app import create_app
    from config.settings import settings
    from utils.logger import get_logger

logger = get_logger(__name__)
app = create_app()

if __name__ == "__main__":
    import os
    logger.info("[MAIN] Starting IRIS AI Backend in single-process mode (PID=%d)", os.getpid())
    print("SERVER_READY", flush=True)
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,
        workers=1,
        log_level="debug" if settings.DEBUG else "info",
    )
