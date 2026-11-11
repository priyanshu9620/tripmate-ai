"""`tm` command line: serve the API, or chat with a running server."""

import httpx
import typer
import uvicorn
from rich.console import Console

from tripmate.config import settings

tools_app = typer.Typer(help="Inspect the agents' tools without an LLM")

app = typer.Typer(no_args_is_help=True, help="TripMate AI")
app.add_typer(tools_app, name="tools")
console = Console()


@app.command()
def serve(host: str = settings.host, port: int = settings.port) -> None:
    """Run the API (http://<host>:<port>/ui for the chat page)."""
    uvicorn.run("tripmate.api:app", host=host, port=port)


@app.command()
def chat(url: str = "http://127.0.0.1:8000") -> None:
    """Interactive chat against a running server. Ctrl-D to quit."""
    with httpx.Client(base_url=url, timeout=120) as client:
        tid = client.post("/threads").raise_for_status().json()["thread_id"]
        console.print(f"[dim]thread {tid}[/dim]")
        while True:
            try:
                text = console.input("[bold cyan]you>[/bold cyan] ")
            except EOFError:
                break
            if not text.strip():
                continue
            r = client.post(f"/threads/{tid}/messages", json={"content": text}).raise_for_status()
            console.print(f"[bold green]tripmate>[/bold green] {r.json()['reply']}")


@tools_app.command("demo")
def tools_demo(
    origin: str = "Delhi", destination: str = "Goa", start: str = "", nights: int = 4, travellers: int = 2
) -> None:
    """Run every read tool for one trip and print the results (TOOLS_MODE=offline|live from .env)."""
    from datetime import date, timedelta

    from rich.table import Table

    from tripmate.tools import geocode, points_of_interest, search_flights, search_hotels, weather_forecast

    d0 = date.fromisoformat(start) if start else date.today() + timedelta(days=30)
    d1 = d0 + timedelta(days=nights)
    console.print(f"[dim]tools_mode={settings.tools_mode}[/dim]")
    console.print("geocode:", geocode.invoke({"place": destination}))
    for title, res, cols in (
        (
            "weather",
            weather_forecast.invoke({"place": destination, "start_date": str(d0), "end_date": str(d1)}),
            ["date", "tmax_c", "tmin_c", "rain_pct", "summary"],
        ),
        ("points of interest", points_of_interest.invoke({"place": destination}), ["name", "kind"]),
        (
            "flights",
            search_flights.invoke(
                {
                    "origin": origin,
                    "destination": destination,
                    "travel_date": str(d0),
                    "passengers": travellers,
                }
            ),
            ["flight_id", "airline", "depart", "duration_min", "stops", "price_per_person_inr", "total_inr"],
        ),
        (
            "hotels",
            search_hotels.invoke(
                {"destination": destination, "checkin": str(d0), "checkout": str(d1), "guests": travellers}
            ),
            ["hotel_id", "name", "tier", "rating", "rate_per_night_inr", "total_inr"],
        ),
    ):
        t = Table(title=f"{title} · {res.get('count', 0)} · {res.get('source', res.get('error'))}")
        for c in cols:
            t.add_column(c)
        for row in res.get("items", [])[:8]:
            t.add_row(*(str(row.get(c, "")) for c in cols))
        console.print(t)
