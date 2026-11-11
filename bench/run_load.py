"""Load benchmark driver: runs bench/load.js (k6 in Docker) at several fixed VU levels against the running API,
which must use LLM_PROVIDER=fake (this measures FastAPI + LangGraph + Postgres checkpointing + the tool layer,
NOT the LLM). Writes bench/out/load-<ts>.json.

    LLM_PROVIDER=fake docker compose up -d --build api   # then:
    uv run python bench/run_load.py [--vus 2,5,10,20] [--duration 30s]"""

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

K6_IMAGE = "grafana/k6:0.57.0"
HERE = Path(__file__).resolve().parent
OUT = HERE / "out"


def run_level(vus: int, duration: str, tmp: Path) -> dict:
    summary = tmp / f"k6-{vus}.json"
    cmd = [
        "docker", "run", "--rm", "-i", "--add-host=host.docker.internal:host-gateway",
        "-v", f"{HERE}:/bench:ro", "-v", f"{tmp}:/out",
        "-e", f"VUS={vus}", "-e", f"DURATION={duration}",
        K6_IMAGE, "run", "--quiet", "--summary-export", f"/out/{summary.name}", "/bench/load.js",
    ]  # fmt: skip
    p = subprocess.run(cmd, capture_output=True, text=True)
    if not summary.exists():
        print(p.stdout[-2000:], p.stderr[-2000:])
        raise SystemExit("k6 produced no summary")
    s = json.loads(summary.read_text())
    m = s["metrics"]

    def pct(name: str, key: str) -> float | None:
        return round(m[name][key], 1) if name in m and key in m[name] else None

    reqs = m["http_reqs"]["count"]
    iters = m["iterations"]["count"]
    dur_s = float(duration.rstrip("s"))
    return {
        "vus": vus,
        "duration_s": dur_s,
        "iterations": iters,
        "trips_per_s": round(iters / dur_s, 2),
        "http_reqs": reqs,
        "rps": round(reqs / dur_s, 1),
        "failed_rate": round(m["http_req_failed"]["value"], 4),
        "http_req_duration_ms": {k: pct("http_req_duration", k) for k in ("med", "p(90)", "p(95)", "max")},
        "plan_ms": {k: pct("http_req_duration{name:plan}", k) for k in ("med", "p(95)")},
        "approve_ms": {k: pct("http_req_duration{name:approve}", k) for k in ("med", "p(95)")},
        "checks_pass_rate": round(m["checks"]["value"], 4) if "checks" in m else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vus", default="2,5,10,20")
    ap.add_argument("--duration", default="30s")
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    h = httpx.get(f"{args.url}/healthz", timeout=5).json()
    if h["llm_provider"] != "fake":
        print(f"API runs llm_provider={h['llm_provider']}; the load bench needs fake. Aborting.")
        return 2
    run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    tmp = OUT / f"k6-{run_id}"
    tmp.mkdir(parents=True, exist_ok=True)
    print(f"load bench · fake LLM · memory {h['memory']} · VUs {args.vus} × {args.duration} · run {run_id}")
    levels = []
    for vus in (int(v) for v in args.vus.split(",")):
        r = run_level(vus, args.duration, tmp)
        levels.append(r)
        d = r["http_req_duration_ms"]
        print(
            f"  {vus:>3} VUs: {r['trips_per_s']:>5} trips/s  {r['rps']:>6} req/s  "
            f"p50 {d['med']} ms  p95 {d['p(95)']} ms  errors {r['failed_rate'] * 100:.2f}%"
        )
    # headline: highest VU level with p95 < 500 ms and errors < 1 %
    ok = [lv for lv in levels if lv["http_req_duration_ms"]["p(95)"] < 500 and lv["failed_rate"] < 0.01]
    best = max(ok, key=lambda lv: lv["vus"]) if ok else None  # highest concurrency still inside the SLO
    summary = {
        "run_id": run_id,
        "memory": h["memory"],
        "llm": "fake (scripted)",
        "levels": levels,
        "best_within_slo": best,
    }
    path = OUT / f"load-{run_id}.json"
    path.write_text(json.dumps(summary, indent=1))
    print(f"\nbest within SLO (p95<500 ms, errors<1 %): {best['vus'] if best else 'none'} VUs → {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
