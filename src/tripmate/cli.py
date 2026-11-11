"""`tm` command line: serve the API, or chat with a running server."""

import httpx
import typer
import uvicorn
from rich.console import Console

from tripmate.config import settings

app = typer.Typer(no_args_is_help=True, help="TripMate AI")
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
