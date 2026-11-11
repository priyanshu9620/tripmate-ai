"""Needs a reachable Postgres (make up → localhost:5433, or the CI service). Skipped otherwise."""

import uuid

import pytest
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from tripmate import db
from tripmate.fake_llm import ScriptedTripModel
from tripmate.graph import build_graph
from tripmate.providers import bookings

pytestmark = pytest.mark.skipif(not db.ping(), reason="postgres not reachable")
ASK = "Plan a trip from Delhi to Goa, 2026-12-18, 4 days, 2 people, budget ₹60,000. We like beaches."


def test_state_survives_a_new_process_and_prefs_cross_threads():
    bookings.reset()
    tid, user = uuid.uuid4().hex[:12], "pg-" + uuid.uuid4().hex[:6]
    mem = db.Memory()
    mem.setup()
    g = build_graph(
        ScriptedTripModel(), mem.checkpointer, lambda: mem.load_prefs(user), lambda p: mem.save_prefs(user, p)
    )
    out = g.invoke({"messages": [HumanMessage(content=ASK)]}, {"configurable": {"thread_id": tid}})
    assert out["phase"] == "await_approval"
    mem.close()

    # "restart": brand-new pool, checkpointer and graph; the interrupt is still pending in Postgres
    mem2 = db.Memory()
    g2 = build_graph(
        ScriptedTripModel(),
        mem2.checkpointer,
        lambda: mem2.load_prefs(user),
        lambda p: mem2.save_prefs(user, p),
    )
    snap = g2.get_state({"configurable": {"thread_id": tid}})
    assert any(t.interrupts for t in snap.tasks)
    out = g2.invoke(Command(resume={"decision": "approve"}), {"configurable": {"thread_id": tid}})
    assert out["phase"] == "done" and all(b["ok"] for b in out["bookings"])

    trip = mem2.save_trip(tid, user, out)
    assert trip["thread_id"] == tid and mem2.save_trip(tid, user, out)["id"] == trip["id"]  # idempotent
    assert mem2.list_trips(user)[0]["id"] == trip["id"]

    # cross-thread preference memory: a new thread for the same user starts with "beach"
    assert mem2.load_prefs(user) == ["beach"]
    out = g2.invoke(
        {
            "messages": [
                HumanMessage(
                    content="Plan a trip from Mumbai to Jaipur, 2027-01-10, 3 days, 2 people, ₹50000"
                )
            ]
        },
        {"configurable": {"thread_id": uuid.uuid4().hex[:12]}},
    )
    assert "beach" in out["constraints"]["preferences"]
    mem2.close()
