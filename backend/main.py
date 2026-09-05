"""
IRIS AI Backend Entry Point
Run from the repo root:  python -m backend.main
  or from backend/:      python main.py
"""
import sys
import io
import os
import types

if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

if not getattr(sys, "frozen", False):
    repo_root = os.path.abspath(os.path.join(base_dir, ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

# If "backend" is not in sys.modules, configure package path for PyInstaller PYZ resolution
backend_pkg_path = os.path.join(base_dir, "backend")
if "backend" not in sys.modules:
    pkg = types.ModuleType("backend")
    pkg.__path__ = [backend_pkg_path, base_dir]
    sys.modules["backend"] = pkg
elif hasattr(sys.modules["backend"], "__path__"):
    if backend_pkg_path not in sys.modules["backend"].__path__:
        sys.modules["backend"].__path__.insert(0, backend_pkg_path)
    if base_dir not in sys.modules["backend"].__path__:
        sys.modules["backend"].__path__.append(base_dir)

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
