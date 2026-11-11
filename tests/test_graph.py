from langchain_core.messages import HumanMessage
from langgraph.types import Command

from tripmate.agents.nodes import route
from tripmate.agents.state import Constraints
from tripmate.fake_llm import ScriptedTripModel
from tripmate.graph import build_graph
from tripmate.providers import bookings

ASK = "Plan a trip from Delhi to Goa, 2026-12-18, 4 days, 2 people, budget ₹60,000. We like beaches."


def setup_function():
    bookings.reset()


def test_supervisor_routing_is_pure_code():
    assert route({"phase": "collect"}) == "__end__"
    assert route({"phase": "research"}) == "researcher"
    assert route({"phase": "plan"}) == "planner"
    assert route({"phase": "budget"}) == "budgeter"
    assert route({"phase": "await_approval"}) == "approval"
    assert route({"phase": "book"}) == "booker"
    assert route({}) == "__end__"


def test_constraints_merge_and_dates():
    c = Constraints(destination="Goa", days=4, start_date="2026-12-18", preferences=["beach"])
    assert set(c.missing()) == {"origin", "travellers", "budget_inr"}
    c = c.merge(
        {"origin": "Delhi", "travellers": ["A", "B"], "budget_inr": 60000, "preferences": ["beach", "food"]}
    )
    assert c.missing() == [] and c.nights == 3 and c.end.isoformat() == "2026-12-21"
    assert c.preferences == ["beach", "food"]


def test_intake_asks_for_missing_fields_then_proceeds():
    g = build_graph(ScriptedTripModel())
    cfg = {"configurable": {"thread_id": "t-ask"}}
    out = g.invoke({"messages": [HumanMessage(content="I want to go to Goa for 4 days")]}, cfg)
    assert out["phase"] == "collect"
    assert "origin" in out["messages"][-1].text and "budget_inr" in out["messages"][-1].text
    out = g.invoke(
        {"messages": [HumanMessage(content="from Delhi to Goa on 2026-12-18, 2 people, ₹60000")]}, cfg
    )
    assert out["phase"] == "await_approval" and "__interrupt__" in out


def test_full_flow_pauses_for_approval_then_books():
    g = build_graph(ScriptedTripModel())
    cfg = {"configurable": {"thread_id": "t-full"}}
    out = g.invoke({"messages": [HumanMessage(content=ASK)]}, cfg)
    assert out["phase"] == "await_approval"
    intr = out["__interrupt__"][0].value
    assert intr["type"] == "approval_request" and intr["proposal"]["within_budget"] is True
    assert len(out["itinerary"]["days"]) == 4
    assert out["research"]["pois"]["count"] >= 8  # unfiltered: the planner gets variety
    assert "Beach" in out["itinerary"]["days"][0]["activities"][0]  # preferences steer the plan
    assert out["usage"]["llm_calls"] >= 5 and out["usage"]["tool_calls"] == 6
    assert bookings.all_bookings() == []  # nothing booked before approval
    out = g.invoke(Command(resume={"decision": "approve"}), cfg)
    assert out["phase"] == "done" and len(out["bookings"]) == 3 and all(b["ok"] for b in out["bookings"])
    assert out["messages"][-1].text.startswith("Booked!")
    assert len(bookings.all_bookings()) == 3


def test_reject_with_feedback_replans_then_gives_up_after_two():
    g = build_graph(ScriptedTripModel())
    cfg = {"configurable": {"thread_id": "t-rej"}}
    g.invoke({"messages": [HumanMessage(content=ASK)]}, cfg)
    out = g.invoke(Command(resume={"decision": "reject", "feedback": "cheaper hotel"}), cfg)
    assert out["phase"] == "await_approval" and out["rejections"] == 1
    out = g.invoke(Command(resume={"decision": "reject", "feedback": "still no"}), cfg)
    assert out["rejections"] == 2 and "__interrupt__" in out
    out = g.invoke(Command(resume={"decision": "reject"}), cfg)
    assert out["phase"] == "collect" and "stopped" in out["messages"][-1].text
    assert bookings.all_bookings() == []


def test_over_budget_is_flagged_not_hidden():
    g = build_graph(ScriptedTripModel())
    cfg = {"configurable": {"thread_id": "t-poor"}}
    out = g.invoke({"messages": [HumanMessage(content=ASK.replace("₹60,000", "₹5,000"))]}, cfg)
    p = out["__interrupt__"][0].value["proposal"]
    assert p["within_budget"] is False and "OVER BUDGET" in out["__interrupt__"][0].value["summary"]


def test_budgeter_respects_seats_and_rooms_for_a_group_of_six():
    g = build_graph(ScriptedTripModel())
    cfg = {"configurable": {"thread_id": "t-six"}}
    out = g.invoke(
        {
            "messages": [
                HumanMessage(
                    content="Trip from Delhi to Jaipur, 2027-01-15, 3 days, 6 people, budget ₹120000"
                )
            ]
        },
        cfg,
    )
    p = out["__interrupt__"][0].value["proposal"]
    assert (
        p["outbound"]["seats_left"] >= 6 and p["return"]["seats_left"] >= 6 and p["hotel"]["rooms_left"] >= 3
    )
    out = g.invoke(Command(resume={"decision": "approve"}), cfg)
    assert out["phase"] == "done" and all(b["ok"] for b in out["bookings"])
