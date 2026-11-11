"""Deterministic quality checks on a finished graph state. No LLM-as-judge: every check is a rule derived from
the scenario, so two runs of the same scenario are comparable and a failure points at a concrete field."""

from datetime import date, timedelta

from tripmate.providers.catalog import resolve_place


def check(scenario: dict, state: dict, bookings_ok: bool) -> dict[str, bool]:
    c = state.get("constraints") or {}
    it = (state.get("itinerary") or {}).get("days") or []
    p = state.get("proposal") or {}
    pois = {x["name"] for x in ((state.get("research") or {}).get("pois") or {}).get("items", [])}
    start = date.fromisoformat(scenario["start_date"])
    end = start + timedelta(days=max(1, scenario["days"] - 1))
    want_dates = [(start + timedelta(days=i)).isoformat() for i in range(scenario["days"])]
    try:
        o_air = resolve_place(scenario["origin"])[1]["airport"]
        d_air = resolve_place(scenario["destination"])[1]["airport"]
    except ValueError:
        o_air = d_air = None
    out, ret, hotel = p.get("outbound") or {}, p.get("return") or {}, p.get("hotel") or {}
    results = {
        "constraints_extracted": (
            c.get("days") == scenario["days"]
            and c.get("start_date") == scenario["start_date"]
            and len(c.get("travellers") or []) == scenario["travellers"]
            and c.get("budget_inr") == scenario["budget_inr"]
            and _same_place(c.get("destination"), scenario["destination"])
            and _same_place(c.get("origin"), scenario["origin"])
        ),
        "reached_approval": bool(p),
        "day_count": len(it) == scenario["days"],
        "dates_in_order": [d.get("date") for d in it] == want_dates,
        "every_day_has_activity": bool(it) and all(len(d.get("activities") or []) >= 1 for d in it),
        "activities_are_real_sights": bool(it)
        and all(a in pois for d in it for a in (d.get("activities") or [])),
        "no_sight_repeated": bool(it)
        and len([a for d in it for a in d.get("activities", [])])
        == len({a for d in it for a in d.get("activities", [])}),
        "flights_match_route_and_dates": (
            out.get("from") == o_air
            and out.get("to") == d_air
            and out.get("date") == start.isoformat()
            and ret.get("from") == d_air
            and ret.get("to") == o_air
            and ret.get("date") == end.isoformat()
        ),
        "hotel_matches_stay": hotel.get("checkin") == start.isoformat()
        and hotel.get("checkout") == end.isoformat()
        and hotel.get("nights") == max(1, scenario["days"] - 1),
        "total_is_consistent": bool(p)
        and p.get("total_inr")
        == (out.get("price_per_person_inr", 0) + ret.get("price_per_person_inr", 0)) * scenario["travellers"]
        + hotel.get("total_inr", 0),
        "budget_verdict_correct": bool(p)
        and p.get("within_budget") == (p.get("total_inr", 10**12) <= scenario["budget_inr"])
        and (not scenario.get("expect_over_budget") or p.get("within_budget") is False),
        "booked_after_approval": bookings_ok,
    }
    return results


def _same_place(a: str | None, b: str) -> bool:
    try:
        return bool(a) and resolve_place(a)[0] == resolve_place(b)[0]
    except ValueError:
        return False
