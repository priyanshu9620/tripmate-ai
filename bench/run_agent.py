"""Agent benchmark: run every scenario through the real graph (in-process, in-memory checkpointer) up to the
approval interrupt, approve, and score with bench/checks.py. Writes bench/out/agent-<provider>-<model>-<ts>.json.

    uv run python bench/run_agent.py                # provider/model from .env
    uv run python bench/run_agent.py --provider fake
    uv run python bench/run_agent.py --limit 3

Stops after 3 consecutive infrastructure errors (quota, network) and writes NO results file in that case."""

import argparse
import json
import os
import sys
import time
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path

import yaml
from langchain_core.messages import HumanMessage
from langgraph.types import Command

sys.path.insert(0, str(Path(__file__).resolve().parent))
from checks import check  # noqa: E402

from tripmate.config import settings  # noqa: E402
from tripmate.graph import build_graph  # noqa: E402
from tripmate.llm import get_model  # noqa: E402
from tripmate.providers import bookings  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
# USD per 1M tokens (input, output). Free tiers cost 0 while within quota; we report both.
PRICES = {
    "gemini-3.5-flash-lite": (0.10, 0.40),
    "gemini-3.8-flash": (0.30, 2.50),
    "claude-sonnet-5-5": (3.0, 15.0),
    "claude-haiku-5-5": (0.80, 4.0),
    "openai/gpt-oss-120b": (0.15, 0.60),
}


def root_cause(e: BaseException) -> str:
    while isinstance(e, BaseExceptionGroup) and e.exceptions:
        e = e.exceptions[0]
    while e.__cause__ is not None:
        e = e.__cause__
    return f"{type(e).__name__}: {str(e)[:300]}"


def run_one(graph, scenario: dict) -> dict:
    tid = f"bench-{scenario['id']}-{uuid.uuid4().hex[:6]}"
    cfg = {"configurable": {"thread_id": tid}}
    t0 = time.perf_counter()
    bookings.reset()
    state = graph.invoke({"messages": [HumanMessage(content=scenario["ask"])]}, cfg)
    t_proposal = time.perf_counter() - t0
    reached = "__interrupt__" in state
    bookings_ok = False
    if reached:
        state = graph.invoke(Command(resume={"decision": "approve"}), cfg)
        bookings_ok = state.get("phase") == "done" and all(b.get("ok") for b in state.get("bookings") or [])
    total = time.perf_counter() - t0
    checks = check(scenario, state, bookings_ok)
    u = state.get("usage") or {}
    return {
        "id": scenario["id"],
        "thread_id": tid,
        "latency_to_proposal_s": round(t_proposal, 2),
        "latency_total_s": round(total, 2),
        "llm_calls": u.get("llm_calls", 0),
        "tool_calls": u.get("tool_calls", 0),
        "input_tokens": u.get("input_tokens", 0),
        "output_tokens": u.get("output_tokens", 0),
        "total_inr": (state.get("proposal") or {}).get("total_inr"),
        "within_budget": (state.get("proposal") or {}).get("within_budget"),
        "checks": checks,
        "passed": sum(checks.values()),
        "of": len(checks),
        "reply": (state["messages"][-1].text[:200] if state.get("messages") else ""),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=settings.llm_provider)
    ap.add_argument("--model", default=settings.llm_model)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    scenarios = yaml.safe_load((Path(__file__).resolve().parent / "scenarios.yml").read_text())
    for sc in scenarios:
        sc["start_date"] = str(sc["start_date"])  # YAML parses bare dates as date objects
    if args.limit:
        scenarios = scenarios[: args.limit]
    run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    model_name = "scripted" if args.provider == "fake" else args.model
    os.environ.setdefault("LANGSMITH_PROJECT", "tripmate-ai")
    graph = build_graph(get_model(args.provider, args.model))
    print(
        f"agent bench · {args.provider}/{model_name} · tools {settings.tools_mode} · {len(scenarios)} scenarios · run {run_id}"
    )

    rows, infra_errors, streak = [], [], 0
    for sc in scenarios:
        try:
            from langsmith import tracing_context

            with tracing_context(tags=["bench", run_id, sc["id"], args.tag or model_name]):
                row = run_one(graph, sc)
            streak = 0
        except Exception as e:  # noqa: BLE001
            cause = root_cause(e)
            infra_errors.append({"id": sc["id"], "error": cause})
            streak += 1
            print(f"  {sc['id']:<26} ERROR {cause}")
            if streak >= 3:
                print("3 consecutive errors — aborting, no results file written (not a model result).")
                traceback.print_exc(limit=2)
                return 2
            continue
        rows.append(row)
        failed = [k for k, v in row["checks"].items() if not v]
        print(
            f"  {row['id']:<26} {row['passed']:>2}/{row['of']}  {row['latency_to_proposal_s']:>6.1f}s  "
            f"{row['llm_calls']} llm {row['tool_calls']} tools  {row['input_tokens']}/{row['output_tokens']} tok"
            + (f"  ✗ {', '.join(failed)}" if failed else "")
        )

    if not rows:
        return 2
    lat = sorted(r["latency_to_proposal_s"] for r in rows)
    pin, pout = PRICES.get(model_name, (0.0, 0.0))
    tok_in, tok_out = sum(r["input_tokens"] for r in rows), sum(r["output_tokens"] for r in rows)
    check_names = list(rows[0]["checks"])
    summary = {
        "run_id": run_id,
        "provider": args.provider,
        "model": model_name,
        "tools_mode": settings.tools_mode,
        "scenarios": len(scenarios),
        "completed": len(rows),
        "infra_errors": infra_errors,
        "fully_passed": sum(1 for r in rows if r["passed"] == r["of"]),
        "checks_passed": sum(r["passed"] for r in rows),
        "checks_total": sum(r["of"] for r in rows),
        "per_check_pass_rate": {k: sum(1 for r in rows if r["checks"][k]) / len(rows) for k in check_names},
        "latency_to_proposal_s": {
            "p50": lat[len(lat) // 2],
            "p95": lat[min(len(lat) - 1, int(len(lat) * 0.95))],
            "max": lat[-1],
            "mean": round(sum(lat) / len(lat), 2),
        },
        "llm_calls_per_trip": round(sum(r["llm_calls"] for r in rows) / len(rows), 2),
        "tool_calls_per_trip": round(sum(r["tool_calls"] for r in rows) / len(rows), 2),
        "tokens_per_trip": {"input": round(tok_in / len(rows)), "output": round(tok_out / len(rows))},
        "est_cost_usd_per_trip_at_list_price": round((tok_in * pin + tok_out * pout) / 1e6 / len(rows), 5),
        "rows": rows,
    }
    OUT.mkdir(exist_ok=True)
    path = OUT / f"agent-{args.provider}-{model_name.replace('/', '_')}-{run_id}.json"
    path.write_text(json.dumps(summary, indent=1))
    print(
        f"\n{summary['fully_passed']}/{len(rows)} scenarios fully passed · {summary['checks_passed']}/{summary['checks_total']} checks · "
        f"p50 {summary['latency_to_proposal_s']['p50']}s p95 {summary['latency_to_proposal_s']['p95']}s · "
        f"{summary['tokens_per_trip']['input']}/{summary['tokens_per_trip']['output']} tok/trip · "
        f"${summary['est_cost_usd_per_trip_at_list_price']}/trip at list price\n→ {path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
