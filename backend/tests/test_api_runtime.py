from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.dependencies import get_chat_service
from backend.api.main import app


class FakeChatService:
    """Minimal chat service stub for API integration tests."""

    async def send_message(
        self,
        user_id: str,
        message: str,
        conversation_id: str | None = None,
    ) -> dict[str, str]:
        return {
            "response": f"echo:{message}",
            "conversation_id": conversation_id or "default-conversation",
            "message_id": "fake-message",
        }


def test_health_endpoint() -> None:
    """The health endpoint should return the runtime metadata."""
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "SandSwap AI"
    assert response.json()["version"] == "0.1.0"


def test_chat_endpoint() -> None:
    """The chat endpoint should return the chat-service payload."""
    app.dependency_overrides[get_chat_service] = lambda: FakeChatService()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/chat",
                json={
                    "user_id": "user-1",
                    "conversation_id": "conv-1",
                    "message": "hello",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["response"] == "echo:hello"
    assert response.json()["conversation_id"] == "conv-1"
    assert response.json()["memories_saved"] == 0
