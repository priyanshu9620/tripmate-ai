"""Scripted, rule-based stand-in for the LLM. Dispatches on the `AGENT:` tag of the system prompt and
produces the same kind of output a real model would (JSON, tool calls), deterministically and instantly.
Used by tests, CI and the load bench (`LLM_PROVIDER=fake`)."""

import json
import re
from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from tripmate.jsonutil import extract_json
from tripmate.providers.catalog import place_keys, resolve_place


class ScriptedTripModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "scripted-trip"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ScriptedTripModel":
        return self

    def _generate(
        self,
        messages: Sequence[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        system = next((m.text for m in messages if isinstance(m, SystemMessage)), "")
        agent = re.match(r"AGENT:\s*(\w+)", system)
        name = agent.group(1) if agent else "chat"
        ai = getattr(self, f"_{name}", self._chat)(system, list(messages))
        ai.usage_metadata = {
            "input_tokens": len(system) // 4,
            "output_tokens": len(ai.text) // 4,
            "total_tokens": 0,
        }
        return ChatResult(generations=[ChatGeneration(message=ai)])

    # ---- chat (phase-0 style echo) ----
    def _chat(self, system: str, messages: list[BaseMessage]) -> AIMessage:
        last = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
        return AIMessage(content=f"echo: {last.text}" if last else "echo: (nothing)")

    # ---- intake: regex extraction over the latest human messages ----
    def _intake(self, system: str, messages: list[BaseMessage]) -> AIMessage:
        known = extract_json(system.split("KNOWN:", 1)[1]) if "KNOWN:" in system else {}
        text = " ".join(m.text for m in messages if isinstance(m, HumanMessage))
        out: dict = {"preferences": []}
        low = text.lower()
        stop = r"(?:[,.;]|\s+to\b|\s+on\b|\s+for\b|\s+in\b|\s+\d|$)"
        for field, pattern in (
            ("origin", r"\bfrom\s+([a-z ]+?)" + stop),
            ("destination", r"\bto\s+([a-z ]+?)" + stop),
        ):
            for cand in re.findall(pattern, low):
                try:
                    name = resolve_place(cand)[1]["name"]
                except ValueError:
                    continue
                if name != out.get("origin"):
                    out[field] = name
                    break
        if not out.get("destination") and not (known or {}).get("destination"):
            found = [k for k in place_keys() if re.search(rf"\b{k}\b", low)]
            found = [k for k in found if resolve_place(k)[1]["name"] != out.get("origin")]
            if found:
                out["destination"] = resolve_place(found[0])[1]["name"]
        if m := re.search(r"(\d{4}-\d{2}-\d{2})", text):
            out["start_date"] = m.group(1)
        elif m := re.search(r"in\s+(\d+)\s+days", low):
            out["start_date"] = (date.today() + timedelta(days=int(m.group(1)))).isoformat()
        if m := re.search(r"(\d+)\s*(?:-|\s)?(days?|nights?)", low):
            n = int(m.group(1))
            out["days"] = n + 1 if m.group(2).startswith("night") else n
        if m := re.search(r"(\d+)\s*(?:people|persons?|adults?|travellers?|travelers?|pax|of us)", low):
            out["travellers"] = [f"Traveller {i + 1}" for i in range(int(m.group(1)))]
        if m := re.search(r"(?:₹|rs\.?|inr|budget(?:\s+of)?)\s*([\d,]+)\s*(k)?", low):
            v = int(m.group(1).replace(",", "")) * (1000 if m.group(2) else 1)
            out["budget_inr"] = v
        elif m := re.search(r"([\d,]+)\s*(k)?\s*(?:inr|rupees|budget)", low):
            out["budget_inr"] = int(m.group(1).replace(",", "")) * (1000 if m.group(2) else 1)
        for kind in ("beach", "heritage", "nature", "market", "museum", "food", "adventure", "culture"):
            if kind in low:
                out["preferences"].append(kind)
        merged = {**(known or {}), **{k: v for k, v in out.items() if v not in (None, "", [])}}
        missing = [
            k
            for k in ("origin", "destination", "start_date", "days", "travellers", "budget_inr")
            if not merged.get(k)
        ]
        out["question"] = f"Please tell me: {', '.join(missing)}." if missing else None
        return AIMessage(content=json.dumps(out))

    # ---- researcher: three tool calls, then a summary ----
    def _researcher(self, system: str, messages: list[BaseMessage]) -> AIMessage:
        c = extract_json(system.split("TRIP:", 1)[1]) or {}
        if any(isinstance(m, ToolMessage) for m in messages):
            return AIMessage(content=f"Research done for {c.get('destination')}: see weather and sights.")
        start = date.fromisoformat(c["start_date"])
        end = start + timedelta(days=max(1, c["days"] - 1))
        return AIMessage(
            content="",
            tool_calls=[
                {"name": "geocode", "args": {"place": c["destination"]}, "id": "c1"},
                {
                    "name": "weather_forecast",
                    "args": {"place": c["destination"], "start_date": str(start), "end_date": str(end)},
                    "id": "c2",
                },
                {
                    "name": "points_of_interest",
                    "args": {"place": c["destination"], "limit": 16},
                    "id": "c3",
                },
            ],
        )

    # ---- planner: spread the sights over the days ----
    def _planner(self, system: str, messages: list[BaseMessage]) -> AIMessage:
        c = extract_json(system.split("TRIP:", 1)[1].split("WEATHER:", 1)[0]) or {}
        sights = re.findall(r"'([^']+)'", system.split("SIGHTS:", 1)[1]) if "SIGHTS:" in system else []
        prefs = [p.lower() for p in c.get("preferences", [])]
        sights.sort(key=lambda n: 0 if any(p in n.lower() for p in prefs) else 1)  # preferred sights first
        start = date.fromisoformat(c["start_date"])
        days, i = [], 0
        per_mid = max(1, min(3, len(sights) // max(1, c["days"]))) if sights else 1  # spread, never repeat
        for d in range(c["days"]):
            per = min(2, per_mid) if d in (0, c["days"] - 1) else per_mid
            acts = [sights[(i + k) % len(sights)] for k in range(per)] if sights else ["Free time"]
            i += per
            days.append(
                {"date": (start + timedelta(days=d)).isoformat(), "title": f"Day {d + 1}", "activities": acts}
            )
        return AIMessage(content=json.dumps({"days": days, "notes": "scripted plan"}))

    # ---- budgeter: three searches, then pick the best hotel that fits with the cheapest flights ----
    def _budgeter(self, system: str, messages: list[BaseMessage]) -> AIMessage:
        c = extract_json(system.split("TRIP:", 1)[1]) or {}
        start = date.fromisoformat(c["start_date"])
        end = start + timedelta(days=max(1, c["days"] - 1))
        n = len(c.get("travellers") or [])
        tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
        if not tool_msgs:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_flights",
                        "args": {
                            "origin": c["origin"],
                            "destination": c["destination"],
                            "travel_date": str(start),
                            "passengers": n,
                        },
                        "id": "b1",
                    },
                    {
                        "name": "search_flights",
                        "args": {
                            "origin": c["destination"],
                            "destination": c["origin"],
                            "travel_date": str(end),
                            "passengers": n,
                        },
                        "id": "b2",
                    },
                    {
                        "name": "search_hotels",
                        "args": {
                            "destination": c["destination"],
                            "checkin": str(start),
                            "checkout": str(end),
                            "guests": n,
                        },
                        "id": "b3",
                    },
                ],
            )
        results = [json.loads(m.text) for m in tool_msgs]
        rooms = -(-n // 2)
        out_f = next((f for f in results[0].get("items", []) if f["seats_left"] >= n), None)
        ret_f = next((f for f in results[1].get("items", []) if f["seats_left"] >= n), None)
        hotels = [h for h in results[2].get("items", []) if h["rooms_left"] >= rooms]
        if not (out_f and ret_f and hotels):
            return AIMessage(content=json.dumps({"reasoning": "no inventory"}))
        flights_total = (out_f["price_per_person_inr"] + ret_f["price_per_person_inr"]) * n
        fitting = [h for h in hotels if flights_total + h["total_inr"] <= c["budget_inr"]]
        hotel = max(fitting, key=lambda h: (h["rating"], -h["total_inr"])) if fitting else hotels[0]
        return AIMessage(
            content=json.dumps(
                {
                    "outbound_flight_id": out_f["flight_id"],
                    "return_flight_id": ret_f["flight_id"],
                    "hotel_id": hotel["hotel_id"],
                    "reasoning": "cheapest flights + best-rated hotel that fits"
                    if fitting
                    else "nothing fits; cheapest",
                }
            )
        )
