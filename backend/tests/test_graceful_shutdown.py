"""
Unit and regression tests for IRIS AI Graceful Shutdown endpoint and security authorization.
"""
import pytest
from starlette.testclient import TestClient
from backend.api.app import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    return TestClient(app)


def test_shutdown_endpoint_local_success(client):
    """Localhost client should receive 200 OK and shutting_down status."""
    response = client.post("/api/v1/shutdown")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "shutting_down"
    assert "pid" in data
    assert "message" in data


def test_shutdown_alias_success(client):
    """The /shutdown alias should behave identically to /api/v1/shutdown."""
    response = client.post("/shutdown")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "shutting_down"


def test_shutdown_rejects_remote_clients():
    """Requests originating from non-localhost IPs must be rejected with 403 Forbidden."""
    import asyncio
    from backend.api.app import create_app

    app = create_app()
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/shutdown",
        "headers": [],
        "query_string": b"",
        "client": ("192.168.1.150", 49152),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    status_code = None

    async def send(message):
        nonlocal status_code
        if message["type"] == "http.response.start":
            status_code = message["status"]

    asyncio.run(app(scope, receive, send))
    assert status_code == 403
