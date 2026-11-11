"""Graph nodes. Each agent = one node; the supervisor is `route()` — plain code over the typed state."""

from datetime import date

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import interrupt

from tripmate.agents import prompts
from tripmate.agents.state import Constraints, TripState
from tripmate.agents.toolloop import run_tool_loop
from tripmate.jsonutil import extract_json
from tripmate.providers import flights as flights_provider
from tripmate.providers import hotels as hotels_provider
from tripmate.providers.catalog import place_keys
from tripmate.tools import BUDGET_TOOLS, RESEARCH_TOOLS

MAX_REJECTIONS = 2


def _usage(msg: AIMessage) -> dict:
    u = msg.usage_metadata or {}
    return {
        "llm_calls": 1,
        "input_tokens": u.get("input_tokens", 0),
        "output_tokens": u.get("output_tokens", 0),
    }


def _recent_human(state: TripState) -> list:
    """Only the conversation (human + final assistant messages); tool transcripts are not replayed."""
    return [
        m
        for m in state["messages"]
        if isinstance(m, HumanMessage | AIMessage) and not getattr(m, "tool_calls", None)
    ]


class Nodes:
    def __init__(self, model: BaseChatModel, prefs_loader=None, prefs_saver=None):
        self.model = model
        self.prefs_loader = prefs_loader or (lambda: [])
        self.prefs_saver = prefs_saver or (lambda prefs: None)

    # ---- intake -----------------------------------------------------------------------------------------
    def intake(self, state: TripState) -> dict:
        known = Constraints.model_validate(state.get("constraints") or {})
        if not known.preferences:
            known = known.merge({"preferences": self.prefs_loader()})
        system = prompts.INTAKE.format(
            today=date.today().isoformat(), places=", ".join(place_keys()), known=known.model_dump_json()
        )
        ai = self.model.invoke([SystemMessage(content=system), *_recent_human(state)[-6:]])
        data = extract_json(ai.text) or {}
        question = data.pop("question", None)
        try:
            merged = known.merge(data)
        except ValueError:
            merged = known
        if merged.preferences:
            self.prefs_saver(merged.preferences)
        missing = merged.missing()
        if missing:
            text = question or f"To plan this I still need: {', '.join(missing)}."
            return {
                "constraints": merged.model_dump(),
                "messages": [AIMessage(content=text)],
                "phase": "collect",
                "usage": _usage(ai),
            }
        return {"constraints": merged.model_dump(), "phase": "research", "usage": _usage(ai)}

    # ---- researcher -------------------------------------------------------------------------------------
    def researcher(self, state: TripState) -> dict:
        c = Constraints.model_validate(state["constraints"])
        res = run_tool_loop(
            self.model, RESEARCH_TOOLS, prompts.RESEARCHER.format(constraints=c.model_dump_json()), []
        )
        research = {"summary": res.final.text}
        for tr in res.tool_results:
            research[
                {"geocode": "geo", "weather_forecast": "weather", "points_of_interest": "pois"}[tr["name"]]
            ] = tr["result"]
        return {
            "research": research,
            "phase": "plan",
            "usage": {**res.usage, "tool_calls": len(res.tool_results)},
        }

    # ---- planner ----------------------------------------------------------------------------------------
    def planner(self, state: TripState) -> dict:
        c = Constraints.model_validate(state["constraints"])
        r = state.get("research") or {}
        weather = [
            {"date": w["date"], "rain_pct": w["rain_pct"], "tmax_c": w["tmax_c"]}
            for w in (r.get("weather") or {}).get("items", [])
        ]
        pois = [p["name"] for p in (r.get("pois") or {}).get("items", [])]
        system = prompts.PLANNER.format(
            days=c.days, start_date=c.start_date, constraints=c.model_dump_json(), weather=weather, pois=pois
        )
        ai = self.model.invoke(
            [SystemMessage(content=system), HumanMessage(content="Write the itinerary now.")]
        )
        data = extract_json(ai.text) or {}
        days = data.get("days") if isinstance(data.get("days"), list) else []
        return {
            "itinerary": {"days": days, "notes": data.get("notes", "")},
            "phase": "budget",
            "usage": _usage(ai),
        }

    # ---- budgeter ---------------------------------------------------------------------------------------
    def budgeter(self, state: TripState) -> dict:
        c = Constraints.model_validate(state["constraints"])
        decision = state.get("decision") or {}
        feedback = (
            f"USER FEEDBACK on the last proposal: {decision['feedback']}" if decision.get("feedback") else ""
        )
        system = prompts.BUDGETER.format(
            start_date=c.start_date,
            end_date=c.end.isoformat(),
            origin=c.origin,
            destination=c.destination,
            guests=len(c.travellers),
            budget_inr=c.budget_inr,
            constraints=c.model_dump_json(),
            feedback=feedback,
        )
        res = run_tool_loop(self.model, BUDGET_TOOLS, system, [HumanMessage(content="Find the options now.")])
        pick = extract_json(res.final.text) or {}
        flights_seen: dict[str, dict] = {}
        hotels_seen: dict[str, dict] = {}
        for tr in res.tool_results:
            for item in tr["result"].get("items", []):
                if tr["name"] == "search_flights":
                    flights_seen[item["flight_id"]] = item
                elif tr["name"] == "search_hotels":
                    hotels_seen[item["hotel_id"]] = item
        n = len(c.travellers)
        rooms = -(-n // 2)
        # capacity gate: an option must actually have room for this party, whatever the model picked
        flights_seen = {k: f for k, f in flights_seen.items() if f.get("seats_left", 0) >= n}
        hotels_seen = {k: h for k, h in hotels_seen.items() if h.get("rooms_left", 0) >= rooms}
        out, ret, hotel = (
            flights_seen.get(pick.get("outbound_flight_id")),
            flights_seen.get(pick.get("return_flight_id")),
            hotels_seen.get(pick.get("hotel_id")),
        )
        usage = {**res.usage, "tool_calls": len(res.tool_results)}
        if not (out and ret and hotel):
            # the model named ids no search returned (or without capacity): cheapest valid option, say so
            out = out or _cheapest(flights_seen, c.origin, c.destination)
            ret = ret or _cheapest(flights_seen, c.destination, c.origin)
            hotel = hotel or (
                min(hotels_seen.values(), key=lambda h: h["total_inr"]) if hotels_seen else None
            )
            pick["reasoning"] = (pick.get("reasoning") or "") + " [fallback: cheapest option with capacity]"
        if not (out and ret and hotel):
            msg = "I could not find flights or hotels for this trip. Try different dates or destination."
            return {"messages": [AIMessage(content=msg)], "phase": "collect", "usage": usage}
        total = out["price_per_person_inr"] * n + ret["price_per_person_inr"] * n + hotel["total_inr"]
        if total > c.budget_inr:
            # budget guard: the model proposed over budget — if a within-budget combination exists, take the
            # cheapest flights + best-rated hotel that fits and say so; otherwise keep the pick, flagged
            cheap_out = _cheapest(flights_seen, c.origin, c.destination) or out
            cheap_ret = _cheapest(flights_seen, c.destination, c.origin) or ret
            flights_total = (cheap_out["price_per_person_inr"] + cheap_ret["price_per_person_inr"]) * n
            fitting = [h for h in hotels_seen.values() if flights_total + h["total_inr"] <= c.budget_inr]
            if fitting:
                out, ret = cheap_out, cheap_ret
                hotel = max(fitting, key=lambda h: (h["rating"], -h["total_inr"]))
                total = flights_total + hotel["total_inr"]
                pick["reasoning"] = (
                    pick.get("reasoning") or ""
                ) + " [budget guard: model's pick was over budget; substituted]"
        proposal = {
            "outbound": out,
            "return": ret,
            "hotel": hotel,
            "travellers": c.travellers,
            "breakdown": {
                "flights_inr": (out["price_per_person_inr"] + ret["price_per_person_inr"]) * n,
                "hotel_inr": hotel["total_inr"],
            },
            "total_inr": total,
            "budget_inr": c.budget_inr,
            "within_budget": total <= c.budget_inr,
            "reasoning": pick.get("reasoning", ""),
        }
        return {"proposal": proposal, "phase": "await_approval", "usage": usage}

    # ---- approval (human-in-the-loop) ------------------------------------------------------------------
    def approval(self, state: TripState) -> dict:
        p = state["proposal"]
        payload = {
            "type": "approval_request",
            "summary": (
                f"{p['outbound']['airline']} out {p['outbound']['date']} {p['outbound']['depart']}, "
                f"{p['return']['airline']} back {p['return']['date']} {p['return']['depart']}, "
                f"{p['hotel']['name']} ({p['hotel']['tier']}, {p['hotel']['nights']} nights). "
                f"Total ₹{p['total_inr']:,} vs budget ₹{p['budget_inr']:,}"
                + ("" if p["within_budget"] else " — OVER BUDGET")
            ),
            "proposal": p,
            "itinerary": state.get("itinerary"),
        }
        decision = interrupt(payload)  # graph pauses here; resumes with the user's decision
        if not isinstance(decision, dict):
            decision = {"decision": str(decision)}
        if decision.get("decision") == "approve":
            return {"decision": decision, "phase": "book"}
        rejections = (state.get("rejections") or 0) + 1
        if rejections > MAX_REJECTIONS:
            msg = "No problem — I've stopped here. Tell me new constraints whenever you want to try again."
            return {
                "decision": decision,
                "rejections": rejections,
                "phase": "collect",
                "messages": [AIMessage(msg)],
            }
        return {"decision": decision, "rejections": rejections, "phase": "budget"}

    # ---- booker (deterministic: books exactly what was approved) ---------------------------------------
    def booker(self, state: TripState) -> dict:
        p = state["proposal"]
        names = p["travellers"]
        results = [
            flights_provider.book_flight(p["outbound"]["flight_id"], names),
            flights_provider.book_flight(p["return"]["flight_id"], names),
            hotels_provider.book_hotel(
                p["hotel"]["hotel_id"],
                date.fromisoformat(p["hotel"]["checkin"]),
                date.fromisoformat(p["hotel"]["checkout"]),
                names,
            ),
        ]
        failed = [r for r in results if not r.get("ok")]
        if failed:
            msg = "Booking failed: " + "; ".join(r["error"] for r in failed)
            return {"bookings": results, "messages": [AIMessage(content=msg)], "phase": "collect"}
        refs = ", ".join(r["reference"] for r in results)
        days = state.get("itinerary", {}).get("days", [])
        plan = "\n".join(f"- {d['date']} {d['title']}: {', '.join(d['activities'])}" for d in days)
        msg = f"Booked! References {refs}. Total ₹{p['total_inr']:,}.\n\nYour itinerary:\n{plan}"
        return {"bookings": results, "messages": [AIMessage(content=msg)], "phase": "done"}


def _cheapest(flights: dict[str, dict], origin: str | None, destination: str | None) -> dict | None:
    from tripmate.providers.catalog import resolve_place

    try:
        o, d = resolve_place(origin or "")[1]["airport"], resolve_place(destination or "")[1]["airport"]
    except ValueError:
        return None
    cands = [f for f in flights.values() if f["from"] == o and f["to"] == d]
    return min(cands, key=lambda f: f["price_per_person_inr"]) if cands else None


# ---- supervisor: routing is plain code over the state -----------------------------------------------------
def route(state: TripState) -> str:
    return {
        "collect": "__end__",
        "research": "researcher",
        "plan": "planner",
        "budget": "budgeter",
        "await_approval": "approval",
        "book": "booker",
        "done": "__end__",
    }[state.get("phase") or "collect"]
