"""Durability: N times — new thread → message → awaiting_approval → `docker compose restart api` → approve → done.
Measures whether the pending human-in-the-loop interrupt survives a process kill. Needs `make up`.
Writes bench/out/durability-<ts>.json."""

import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

URL = "http://127.0.0.1:8000"
ASK = "Plan a trip from Delhi to Goa, 2026-12-18, 4 days, 2 people, budget ₹60000. We like beaches."
OUT = Path(__file__).resolve().parent / "out"


def healthy(c: httpx.Client, timeout_s: float = 60) -> float:
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout_s:
        try:
            if c.get("/healthz").status_code == 200:
                return time.perf_counter() - t0
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise SystemExit("API did not come back")


def main(n: int) -> int:
    rows = []
    with httpx.Client(base_url=URL, timeout=120, headers={"X-User": "durability"}) as c:
        h = c.get("/healthz").json()
        print(f"durability · {n} reps · model {h['llm_provider']} · memory {h['memory']}")
        if h["memory"] != "postgres":
            print("memory is not postgres — the test would be meaningless; aborting")
            return 2
        for i in range(1, n + 1):
            tid = c.post("/threads").json()["thread_id"]
            t = c.post(f"/threads/{tid}/messages", json={"content": ASK}).json()
            paused = t["status"] == "awaiting_approval"
            t0 = time.perf_counter()
            subprocess.run(["docker", "compose", "restart", "api"], check=True, capture_output=True)
            downtime = healthy(c)
            after = c.get(f"/threads/{tid}").json()
            still_paused = after.get("status") == "awaiting_approval"
            t2 = c.post(f"/threads/{tid}/approve", json={"decision": "approve"}).json()
            booked = t2.get("status") == "done" and len((t2.get("trip") or {}).get("references") or []) == 3
            ok = paused and still_paused and booked
            rows.append(
                {
                    "rep": i,
                    "thread_id": tid,
                    "paused_before_restart": paused,
                    "paused_after_restart": still_paused,
                    "booked_after_approve": booked,
                    "restart_to_healthy_s": round(downtime, 2),
                    "restart_total_s": round(time.perf_counter() - t0, 2),
                    "ok": ok,
                }
            )
            print(f"  rep {i:>2}: {'PASS' if ok else 'FAIL'}  restart→healthy {downtime:.1f}s  {tid}")
    summary = {
        "run_id": datetime.now(UTC).strftime("%Y%m%d-%H%M%S"),
        "reps": n,
        "passed": sum(r["ok"] for r in rows),
        "restart_to_healthy_s_mean": round(sum(r["restart_to_healthy_s"] for r in rows) / n, 2),
        "rows": rows,
    }
    OUT.mkdir(exist_ok=True)
    path = OUT / f"durability-{summary['run_id']}.json"
    path.write_text(json.dumps(summary, indent=1))
    print(
        f"\n{summary['passed']}/{n} passed · mean restart→healthy {summary['restart_to_healthy_s_mean']}s\n→ {path}"
    )
    return 0 if summary["passed"] == n else 1


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 10))
