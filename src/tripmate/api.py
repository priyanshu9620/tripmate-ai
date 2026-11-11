"""FastAPI surface over the supervisor graph.

POST /threads · POST /threads/{id}/messages · POST /threads/{id}/stream (SSE) · POST /threads/{id}/approve ·
GET /threads/{id} · GET /trips · GET /healthz · GET /metrics · GET /ui
State lives in Postgres (checkpointer + store + trips) when reachable, in memory otherwise (tests, demos)."""

import json
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, Response
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from tripmate import __version__, db
from tripmate.config import settings
from tripmate.graph import build_graph
from tripmate.llm import get_model

log = logging.getLogger("tripmate")
UI_DIR = Path(__file__).parent / "ui"

TURNS = Counter("tripmate_turns_total", "Conversation turns", ["status"])
TURN_LATENCY = Histogram(
    "tripmate_turn_seconds", "Wall time of one turn", buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60)
)
LLM_CALLS = Counter("tripmate_llm_calls_total", "LLM calls")
TOOL_CALLS = Counter("tripmate_tool_calls_total", "Tool calls")
TOKENS = Counter("tripmate_tokens_total", "LLM tokens", ["direction"])


class MessageIn(BaseModel):
    content: str


class Decision(BaseModel):
    decision: Literal["approve", "reject"]
    feedback: str = ""


class TurnOut(BaseModel):
    thread_id: str
    status: Literal["awaiting_input", "awaiting_approval", "done"]
    reply: str
    proposal: dict | None = None
    itinerary: dict | None = None
    trip: dict | None = None
    usage: dict = {}


def create_app(memory: db.Memory | None | Literal["auto"] = "auto", model=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        mem = memory
        if mem == "auto":
            mem = None
            if db.ping():
                try:
                    mem = db.Memory()
                    mem.setup()
                except Exception as e:  # pragma: no cover - startup diagnostics
                    log.warning("postgres memory unavailable, using in-memory: %s", e)
                    mem = None
        app.state.memory = mem
        app.state.memory_backend = "postgres" if mem else "memory"
        app.state.local_trips = []
        app.state.local_prefs = {}
        app.state.model = model or get_model()
        app.state.graph_cache = {}
        yield
        if mem:
            mem.close()

    app = FastAPI(title="TripMate AI", version=__version__, lifespan=lifespan)

    def graph_for(user_id: str):
        mem = app.state.memory
        if mem:
            loader = lambda: mem.load_prefs(user_id)  # noqa: E731
            saver = lambda prefs: mem.save_prefs(user_id, prefs)  # noqa: E731
            checkpointer = mem.checkpointer
        else:
            loader = lambda: app.state.local_prefs.get(user_id, [])  # noqa: E731
            saver = lambda prefs: app.state.local_prefs.__setitem__(user_id, prefs)  # noqa: E731
            checkpointer = app.state.graph_cache.setdefault("_saver", InMemorySaver())
        return build_graph(app.state.model, checkpointer, loader, saver)

    def snapshot(graph, thread_id: str):
        return graph.get_state({"configurable": {"thread_id": thread_id}})

    def status_of(snap) -> str:
        if any(t.interrupts for t in snap.tasks):
            return "awaiting_approval"
        return "done" if (snap.values or {}).get("phase") == "done" else "awaiting_input"

    def turn_out(thread_id: str, user_id: str, snap, usage_before: dict) -> TurnOut:
        v = snap.values or {}
        status = status_of(snap)
        if status == "awaiting_approval":
            reply = next(i.value["summary"] for t in snap.tasks for i in t.interrupts)
            reply = f"Here is my proposal — {reply}. Approve to book, or reject with feedback."
        else:
            ai = [m for m in v.get("messages", []) if isinstance(m, AIMessage) and m.text]
            reply = ai[-1].text if ai else ""
        trip = None
        if status == "done":
            mem = app.state.memory
            if mem:
                trip = mem.save_trip(thread_id, user_id, v)
            else:
                trip = next((t for t in app.state.local_trips if t["thread_id"] == thread_id), None)
                if trip is None:
                    trip = {
                        "thread_id": thread_id,
                        "user_id": user_id,
                        "destination": v["constraints"]["destination"],
                        "total_inr": v["proposal"]["total_inr"],
                        "references": [b["reference"] for b in v["bookings"]],
                    }
                    app.state.local_trips.insert(0, trip)
        usage = v.get("usage") or {}
        delta = {k: usage.get(k, 0) - usage_before.get(k, 0) for k in set(usage) | set(usage_before)}
        LLM_CALLS.inc(delta.get("llm_calls", 0))
        TOOL_CALLS.inc(delta.get("tool_calls", 0))
        TOKENS.labels(direction="in").inc(delta.get("input_tokens", 0))
        TOKENS.labels(direction="out").inc(delta.get("output_tokens", 0))
        TURNS.labels(status=status).inc()
        return TurnOut(
            thread_id=thread_id,
            status=status,
            reply=reply,
            proposal=v.get("proposal") if status != "awaiting_input" else None,
            itinerary=v.get("itinerary") if status != "awaiting_input" else None,
            trip=trip,
            usage=delta,
        )

    def graph_input(graph, thread_id: str, content: str):
        """A message while a proposal is pending = a rejection with that message as feedback."""
        snap = snapshot(graph, thread_id)
        if status_of(snap) == "awaiting_approval":
            return Command(resume={"decision": "reject", "feedback": content}), snap
        return {"messages": [HumanMessage(content=content)]}, snap

    # ---- routes ----------------------------------------------------------------------------------------
    @app.get("/healthz")
    def healthz() -> dict:
        return {
            "version": __version__,
            "llm_provider": settings.llm_provider,
            "tools_mode": settings.tools_mode,
            "memory": app.state.memory_backend,
            "postgres": db.ping(),
        }

    @app.get("/metrics")
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/ui")
    def ui() -> FileResponse:
        return FileResponse(UI_DIR / "index.html")

    @app.post("/threads", status_code=201)
    def create_thread() -> dict:
        return {"thread_id": uuid.uuid4().hex[:12]}

    @app.get("/threads/{thread_id}")
    def get_thread(thread_id: str, x_user: str = Header("demo")) -> dict:
        graph = graph_for(x_user)
        snap = snapshot(graph, thread_id)
        if not snap.values:
            raise HTTPException(404, "unknown thread")
        v = snap.values
        return {
            "thread_id": thread_id,
            "status": status_of(snap),
            "phase": v.get("phase"),
            "constraints": v.get("constraints"),
            "proposal": v.get("proposal"),
            "itinerary": v.get("itinerary"),
            "bookings": v.get("bookings"),
            "usage": v.get("usage"),
            "messages": [
                {"role": "user" if isinstance(m, HumanMessage) else "assistant", "text": m.text}
                for m in v.get("messages", [])
                if isinstance(m, HumanMessage | AIMessage) and m.text
            ],
        }

    @app.post("/threads/{thread_id}/messages", response_model=TurnOut)
    def post_message(thread_id: str, body: MessageIn, x_user: str = Header("demo")) -> TurnOut:
        graph = graph_for(x_user)
        cfg = {"configurable": {"thread_id": thread_id}}
        inp, before = graph_input(graph, thread_id, body.content)
        with TURN_LATENCY.time():
            graph.invoke(inp, cfg)
        return turn_out(
            thread_id, x_user, snapshot(graph, thread_id), (before.values or {}).get("usage") or {}
        )

    @app.post("/threads/{thread_id}/approve", response_model=TurnOut)
    def approve(thread_id: str, body: Decision, x_user: str = Header("demo")) -> TurnOut:
        graph = graph_for(x_user)
        cfg = {"configurable": {"thread_id": thread_id}}
        before = snapshot(graph, thread_id)
        if status_of(before) != "awaiting_approval":
            raise HTTPException(409, "no proposal awaiting approval on this thread")
        with TURN_LATENCY.time():
            graph.invoke(Command(resume=body.model_dump()), cfg)
        return turn_out(
            thread_id, x_user, snapshot(graph, thread_id), (before.values or {}).get("usage") or {}
        )

    @app.post("/threads/{thread_id}/stream")
    async def stream(thread_id: str, body: MessageIn, request: Request, x_user: str = Header("demo")):
        """Server-sent events: one `node` event per agent step, then `final` (same shape as /messages)."""
        graph = graph_for(x_user)
        cfg = {"configurable": {"thread_id": thread_id}}
        inp, before = graph_input(graph, thread_id, body.content)

        async def gen():
            import asyncio

            loop = asyncio.get_running_loop()
            q: asyncio.Queue = asyncio.Queue()

            def run():
                with TURN_LATENCY.time():
                    for update in graph.stream(inp, cfg, stream_mode="updates"):
                        for node, out in update.items():
                            if node == "__interrupt__":
                                continue
                            phase = (out or {}).get("phase") if isinstance(out, dict) else None
                            loop.call_soon_threadsafe(q.put_nowait, ("node", {"node": node, "phase": phase}))
                loop.call_soon_threadsafe(q.put_nowait, ("final", None))

            fut = loop.run_in_executor(None, run)
            while True:
                kind, payload = await q.get()
                if kind == "final":
                    await fut
                    out = turn_out(
                        thread_id,
                        x_user,
                        snapshot(graph, thread_id),
                        (before.values or {}).get("usage") or {},
                    )
                    yield {"event": "final", "data": out.model_dump_json()}
                    return
                yield {"event": kind, "data": json.dumps(payload)}

        return EventSourceResponse(gen())

    @app.get("/trips")
    def trips(x_user: str = Header("demo")) -> dict:
        mem = app.state.memory
        items = (
            mem.list_trips(x_user) if mem else [t for t in app.state.local_trips if t["user_id"] == x_user]
        )
        return {"count": len(items), "items": items}

    return app


app = create_app()
