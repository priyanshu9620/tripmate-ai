from fastapi.testclient import TestClient

from tripmate.api import create_app
from tripmate.providers import bookings

ASK = "Plan a trip from Delhi to Goa, 2026-12-18, 4 days, 2 people, budget ₹60,000. We like beaches."


def client() -> TestClient:
    bookings.reset()
    return TestClient(create_app(memory=None))  # in-memory checkpointer: no Postgres needed


def test_healthz_reports_version_and_backends():
    with client() as c:
        body = c.get("/healthz").json()
    assert body["version"] and body["llm_provider"] == "fake" and body["memory"] == "memory"
    assert isinstance(body["postgres"], bool)


def test_full_conversation_over_http_with_approval():
    with client() as c:
        tid = c.post("/threads").json()["thread_id"]
        assert c.get(f"/threads/{tid}").status_code == 404
        t = c.post(f"/threads/{tid}/messages", json={"content": "Goa for 4 days"}).json()
        assert t["status"] == "awaiting_input" and "origin" in t["reply"]
        assert c.post(f"/threads/{tid}/approve", json={"decision": "approve"}).status_code == 409
        t = c.post(
            f"/threads/{tid}/messages", json={"content": "from Delhi, 2026-12-18, 2 people, ₹60000"}
        ).json()
        assert (
            t["status"] == "awaiting_approval"
            and t["proposal"]["within_budget"]
            and len(t["itinerary"]["days"]) == 4
        )
        assert t["usage"]["tool_calls"] == 6
        # a plain message while pending = reject with feedback → new proposal
        t = c.post(f"/threads/{tid}/messages", json={"content": "something cheaper please"}).json()
        assert t["status"] == "awaiting_approval"
        t = c.post(f"/threads/{tid}/approve", json={"decision": "approve"}).json()
        assert (
            t["status"] == "done" and t["reply"].startswith("Booked!") and len(t["trip"]["references"]) == 3
        )
        s = c.get(f"/threads/{tid}").json()
        assert s["status"] == "done" and s["messages"][0]["role"] == "user"
        assert c.get("/trips").json()["count"] == 1
        assert c.get("/trips", headers={"X-User": "someone-else"}).json()["count"] == 0


def test_stream_emits_node_events_then_final():
    with client() as c:
        tid = c.post("/threads").json()["thread_id"]
        with c.stream("POST", f"/threads/{tid}/stream", json={"content": ASK}) as r:
            events = [line for line in r.iter_lines() if line.startswith("event:")]
    assert events[:4] == ["event: node"] * 4  # intake, researcher, planner, budgeter
    assert events[-1] == "event: final"


def test_metrics_and_ui_are_served():
    with client() as c:
        assert b"tripmate_turns_total" in c.get("/metrics").content
        assert "TripMate AI" in c.get("/ui").text
