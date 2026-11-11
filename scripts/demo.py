"""The 2-minute demo (DEMO.md). Needs the stack up (`make up`).

Usage: uv run python scripts/demo.py [--no-restart]"""

import subprocess
import sys
import time

import httpx
from rich.console import Console
from rich.panel import Panel

URL, USER = "http://127.0.0.1:8000", "demo"
ASK = (
    "Plan a trip from Delhi to Goa, 2026-12-18, 4 days, 2 people (Asha and Ravi), budget ₹60000. "
    "We like beaches and seafood."
)
c = Console()
api = httpx.Client(base_url=URL, timeout=300, headers={"X-User": USER})


def step(n: int, title: str) -> None:
    c.print(Panel(title, title=f"step {n}", style="bold cyan"))
    time.sleep(0.6)


def wait_healthy() -> dict:
    for _ in range(40):
        try:
            return api.get("/healthz").raise_for_status().json()
        except Exception:
            time.sleep(1)
    sys.exit("API not reachable — run `make up` first")


h = wait_healthy()
step(1, f"API up · model {h['llm_provider']} · tools {h['tools_mode']} · memory {h['memory']}")
tid = api.post("/threads").json()["thread_id"]
c.print(f"[dim]thread {tid} · open http://127.0.0.1:8000/ui?thread={tid} to watch[/dim]")

step(2, "One message → intake → researcher (3 tools) → planner → budgeter (3 tools) → PAUSE for approval")
c.print(f"[cyan]you>[/cyan] {ASK}")
t0 = time.time()
with api.stream("POST", f"/threads/{tid}/stream", json={"content": ASK}) as r:
    for line in r.iter_lines():
        if line.startswith("data:") and '"node"' in line:
            c.print(f"  [dim]{line[6:]}[/dim]")
        elif line.startswith("data:") and '"status"' in line:
            import json

            turn = json.loads(line[6:])
c.print(f"[green]tripmate>[/green] {turn['reply']}")
p = turn["proposal"]
bd = p["breakdown"]
c.print(f"  ₹{bd['flights_inr']:,} flights + ₹{bd['hotel_inr']:,} hotel = ₹{p['total_inr']:,}")
c.print(f"  budget ₹{p['budget_inr']:,} → {'within budget' if p['within_budget'] else 'OVER BUDGET'}")
for d in turn["itinerary"]["days"]:
    c.print(f"  {d['date']} {d['title']}: {', '.join(d['activities'])}")
u = turn["usage"]
stats = f"{u['llm_calls']} LLM calls · {u['tool_calls']} tool calls · {u['input_tokens']}/{u['output_tokens']} tok"
c.print(f"  [dim]{time.time() - t0:.1f} s · {stats}[/dim]")
assert turn["status"] == "awaiting_approval", turn

if "--no-restart" not in sys.argv:
    step(3, "Nothing is booked. Kill the API while the approval is pending — state lives in Postgres")
    subprocess.run(["docker", "compose", "restart", "api"], check=True, capture_output=True)
    wait_healthy()
    s = api.get(f"/threads/{tid}").json()
    c.print(f"  after restart: status={s['status']} phase={s['phase']} — the pause survived")

step(4, "Approve → booker books exactly what was approved → trip saved")
turn = api.post(f"/threads/{tid}/approve", json={"decision": "approve"}).json()
c.print(f"[green]tripmate>[/green] {turn['reply'].splitlines()[0]}")
c.print(f"  trip row: {turn['trip']['references']} · ₹{turn['trip']['total_inr']:,}")

step(5, "Memory across trips: a new thread for the same user already knows the preferences")
tid2 = api.post("/threads").json()["thread_id"]
turn = api.post(f"/threads/{tid2}/messages", json={"content": "Jaipur for 3 days"}).json()
st = api.get(f"/threads/{tid2}").json()
c.print(f"[green]tripmate>[/green] {turn['reply']}")
c.print(f"  [dim]constraints so far: {st['constraints']}[/dim]")
trips = api.get("/trips").json()
c.print(
    Panel(
        f"{trips['count']} trip(s) booked for user {USER}: "
        + ", ".join(f"{t['destination']} ₹{t['total_inr']:,}" for t in trips["items"]),
        style="green",
    )
)
