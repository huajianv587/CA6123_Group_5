from fastapi.testclient import TestClient

from backend.main import app
from shared.database import init_db


def test_health():
    client = TestClient(app)
    assert client.get("/api/health").json()["status"] == "ok"


def test_chat_response_includes_m1_routing_fields():
    init_db()
    client = TestClient(app)

    response = client.post("/api/chat", json={"message": "你好"})
    payload = response.json()

    assert response.status_code == 200
    assert {"success", "session_id", "response", "intent", "agent"} <= set(payload)
    assert payload["intent"] == "unknown"
    assert payload["agent"] == "router"
    assert isinstance(payload["routing_trace"], list)
    assert isinstance(payload["candidate_intents"], list)
    assert "router_confidence" in payload
