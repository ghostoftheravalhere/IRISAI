"""
IRIS AI Backend Entry Point
Starts the FastAPI server using uvicorn.
"""
import uvicorn
from backend.api.app import create_app
from backend.config.settings import settings

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )
