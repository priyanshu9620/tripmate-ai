from datetime import date, timedelta
from typing import Annotated

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field

REQUIRED = ("origin", "destination", "start_date", "days", "travellers", "budget_inr")


class Constraints(BaseModel):
    origin: str | None = None
    destination: str | None = None
    start_date: str | None = None  # ISO
    days: int | None = Field(default=None, ge=1, le=30)
    travellers: list[str] = Field(default_factory=list)
    budget_inr: int | None = Field(default=None, ge=1000)
    preferences: list[str] = Field(default_factory=list)

    def missing(self) -> list[str]:
        out = []
        for k in REQUIRED:
            v = getattr(self, k)
            if v in (None, "", []):
                out.append(k)
        return out

    @property
    def start(self) -> date:
        return date.fromisoformat(self.start_date)

    @property
    def end(self) -> date:
        """Day of the return flight / hotel checkout."""
        return self.start + timedelta(days=max(1, self.days - 1))

    @property
    def nights(self) -> int:
        return max(1, self.days - 1)

    def merge(self, update: dict) -> "Constraints":
        data = self.model_dump()
        for k, v in update.items():
            if k not in data or v in (None, "", []):
                continue
            if k == "preferences":
                data[k] = list(dict.fromkeys([*data[k], *v]))
            else:
                data[k] = v
        return Constraints.model_validate(data)


def _merge_dict(a: dict | None, b: dict | None) -> dict:
    return {**(a or {}), **(b or {})}


def _sum(a: dict | None, b: dict | None) -> dict:
    out = dict(a or {})
    for k, v in (b or {}).items():
        out[k] = out.get(k, 0) + v
    return out


class TripState(MessagesState):
    constraints: dict  # Constraints.model_dump()
    research: Annotated[dict, _merge_dict]  # geo / weather / pois / summary
    itinerary: dict  # {"days": [{"date", "title", "activities": [..]}], "notes"}
    proposal: dict  # {"outbound", "return", "hotel", "total_inr", "within_budget", "breakdown"}
    bookings: list
    decision: dict  # {"decision": approve|reject, "feedback": str}
    rejections: int
    usage: Annotated[dict, _sum]  # llm_calls, input_tokens, output_tokens, tool_calls
    phase: str  # collect | research | plan | budget | await_approval | book | done
