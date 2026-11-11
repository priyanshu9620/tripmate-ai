"""FastAPI surface. Phase 0: threads + messages over the one-node graph, /healthz, /metrics, /ui."""

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from langchain_core.messages import HumanMessage
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel

from tripmate import __version__, db
from tripmate.config import settings
from tripmate.graph import build_graph
from tripmate.llm import get_model

UI_DIR = Path(__file__).parent / "ui"

MESSAGES = Counter("tripmate_messages_total", "Messages handled", ["status"])
TURN_LATENCY = Histogram("tripmate_turn_seconds", "Wall time of one conversation turn")


class MessageIn(BaseModel):
    content: str


class MessageOut(BaseModel):
    thread_id: str
    reply: str


def create_app() -> FastAPI:
    app = FastAPI(title="TripMate AI", version=__version__)
    app.state.graph = build_graph(get_model())
    app.state.threads: set[str] = set()

    @app.get("/healthz")
    def healthz() -> dict:
        return {
            "version": __version__,
            "llm_provider": settings.llm_provider,
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
        tid = uuid.uuid4().hex[:12]
        app.state.threads.add(tid)
        return {"thread_id": tid}

    @app.post("/threads/{thread_id}/messages", response_model=MessageOut)
    def post_message(thread_id: str, body: MessageIn) -> MessageOut:
        if thread_id not in app.state.threads:
            raise HTTPException(404, "unknown thread")
        with TURN_LATENCY.time():
            try:
                result = app.state.graph.invoke(
                    {"messages": [HumanMessage(content=body.content)]},
                    config={"configurable": {"thread_id": thread_id}},
                )
            except Exception:
                MESSAGES.labels(status="error").inc()
                raise
        MESSAGES.labels(status="ok").inc()
        return MessageOut(thread_id=thread_id, reply=result["messages"][-1].text)

    return app


app = create_app()
