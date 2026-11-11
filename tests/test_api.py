from fastapi.testclient import TestClient

from tripmate.api import create_app


def client() -> TestClient:
    return TestClient(create_app())


def test_healthz_reports_version_and_db_state():
    body = client().get("/healthz").json()
    assert body["version"] and body["llm_provider"] == "fake"
    assert body["postgres"] is False  # conftest points at an unreachable port


def test_chat_round_trip_and_unknown_thread():
    c = client()
    tid = c.post("/threads").json()["thread_id"]
    r = c.post(f"/threads/{tid}/messages", json={"content": "plan goa"})
    assert r.status_code == 200 and r.json()["reply"] == "echo: plan goa"
    assert c.post("/threads/nope/messages", json={"content": "x"}).status_code == 404


def test_metrics_and_ui_are_served():
    c = client()
    assert b"tripmate_messages_total" in c.get("/metrics").content
    assert "TripMate AI" in c.get("/ui").text
