"""`tm` command line: serve the API, chat with a running server, approve, list trips, inspect tools."""

import httpx
import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from tripmate.config import settings

app = typer.Typer(no_args_is_help=True, help="TripMate AI")
tools_app = typer.Typer(help="Inspect the agents' tools without an LLM")
app.add_typer(tools_app, name="tools")
console = Console()


def _client(url: str, user: str) -> httpx.Client:
    return httpx.Client(base_url=url, timeout=300, headers={"X-User": user})


def _show(turn: dict) -> None:
    console.print(f"[bold green]tripmate>[/bold green] {turn['reply']}")
    if turn["status"] == "awaiting_approval":
        p = turn["proposal"]
        console.print(
            f"  [dim]₹{p['breakdown']['flights_inr']:,} flights + ₹{p['breakdown']['hotel_inr']:,} hotel = "
            f"₹{p['total_inr']:,} (budget ₹{p['budget_inr']:,})[/dim]"
        )
        for d in (turn.get("itinerary") or {}).get("days", []):
            console.print(f"  [dim]{d['date']} {d['title']}: {', '.join(d['activities'])}[/dim]")
    if turn.get("usage"):
        u = turn["usage"]
        console.print(
            f"  [dim]{u.get('llm_calls', 0)} LLM calls · {u.get('tool_calls', 0)} tool calls · "
            f"{u.get('input_tokens', 0)}/{u.get('output_tokens', 0)} tokens[/dim]"
        )


@app.command()
def serve(host: str = settings.host, port: int = settings.port) -> None:
    """Run the API (http://<host>:<port>/ui for the chat page)."""
    uvicorn.run("tripmate.api:app", host=host, port=port)


@app.command()
def chat(url: str = "http://127.0.0.1:8000", user: str = "demo", thread: str = "") -> None:
    """Interactive chat against a running server. While a proposal is pending, 'y' approves, anything else
    is feedback. Ctrl-D to quit."""
    with _client(url, user) as c:
        tid = thread or c.post("/threads").raise_for_status().json()["thread_id"]
        console.print(f"[dim]thread {tid} · user {user} · resume later with: tm chat --thread {tid}[/dim]")
        pending = False
        if thread:
            st = c.get(f"/threads/{tid}")
            if st.status_code == 200:
                pending = st.json()["status"] == "awaiting_approval"
                for m in st.json()["messages"][-4:]:
                    console.print(f"[dim]{m['role']}> {m['text'][:200]}[/dim]")
        while True:
            try:
                text = console.input(
                    "[bold cyan]approve? (y/feedback)>[/bold cyan] "
                    if pending
                    else "[bold cyan]you>[/bold cyan] "
                )
            except EOFError:
                break
            if not text.strip():
                continue
            if pending and text.strip().lower() in {"y", "yes", "approve"}:
                r = c.post(f"/threads/{tid}/approve", json={"decision": "approve"}).raise_for_status()
            else:
                r = c.post(f"/threads/{tid}/messages", json={"content": text}).raise_for_status()
            turn = r.json()
            _show(turn)
            pending = turn["status"] == "awaiting_approval"
            if turn["status"] == "done":
                console.print(f"[dim]trip saved: {turn['trip']}[/dim]")


@app.command()
def approve(
    thread: str,
    reject: bool = False,
    feedback: str = "",
    url: str = "http://127.0.0.1:8000",
    user: str = "demo",
) -> None:
    """Approve (or reject) the proposal pending on a thread."""
    with _client(url, user) as c:
        r = c.post(
            f"/threads/{thread}/approve",
            json={"decision": "reject" if reject else "approve", "feedback": feedback},
        )
        if r.status_code == 409:
            console.print("[red]nothing awaiting approval on that thread[/red]")
            raise typer.Exit(1)
        _show(r.raise_for_status().json())


@app.command()
def trips(url: str = "http://127.0.0.1:8000", user: str = "demo") -> None:
    """List booked trips."""
    with _client(url, user) as c:
        items = c.get("/trips").raise_for_status().json()["items"]
    t = Table(title=f"trips · {len(items)}")
    for col in ("thread_id", "origin", "destination", "start_date", "days", "total_inr", "references"):
        t.add_column(col)
    for i in items:
        t.add_row(
            *(
                str(i.get(col, ""))
                for col in (
                    "thread_id",
                    "origin",
                    "destination",
                    "start_date",
                    "days",
                    "total_inr",
                    "references",
                )
            )
        )
    console.print(t)


@tools_app.command("demo")
def tools_demo(
    origin: str = "Delhi", destination: str = "Goa", start: str = "", nights: int = 4, travellers: int = 2
) -> None:
    """Run every read tool for one trip and print the results (TOOLS_MODE=offline|live from .env)."""
    from datetime import date, timedelta

    from tripmate.tools import geocode, points_of_interest, search_flights, search_hotels, weather_forecast

    d0 = date.fromisoformat(start) if start else date.today() + timedelta(days=30)
    d1 = d0 + timedelta(days=nights)
    console.print(f"[dim]tools_mode={settings.tools_mode}[/dim]")
    console.print("geocode:", geocode.invoke({"place": destination}))
    for title, res, cols in (
        ("weather", weather_forecast.invoke({"place": destination, "start_date": str(d0),
                                             "end_date": str(d1)}),
         ["date", "tmax_c", "tmin_c", "rain_pct", "summary"]),
        ("points of interest", points_of_interest.invoke({"place": destination}), ["name", "kind"]),
        ("flights", search_flights.invoke({"origin": origin, "destination": destination,
                                           "travel_date": str(d0), "passengers": travellers}),
         ["flight_id", "airline", "depart", "duration_min", "stops", "price_per_person_inr", "total_inr"]),
        ("hotels", search_hotels.invoke({"destination": destination, "checkin": str(d0), "checkout": str(d1),
                                         "guests": travellers}),
         ["hotel_id", "name", "tier", "rating", "rate_per_night_inr", "total_inr"]),
    ):  # fmt: skip
        t = Table(title=f"{title} · {res.get('count', 0)} · {res.get('source', res.get('error'))}")
        for c in cols:
            t.add_column(c)
        for row in res.get("items", [])[:8]:
            t.add_row(*(str(row.get(c, "")) for c in cols))
        console.print(t)
