"""Generate bench/report.md + inline-SVG charts + bench/results.json from the newest run of each benchmark in
bench/out/. Also refreshes the measured-numbers table in README.md between the markers. Never hand-edit the report."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
README = HERE.parent / "README.md"


def latest(prefix: str) -> dict | None:
    files = sorted(OUT.glob(f"{prefix}*.json"))
    return json.loads(files[-1].read_text()) if files else None


def latest_agent_runs() -> dict[str, dict]:
    """newest run per model"""
    runs: dict[str, dict] = {}
    for f in sorted(OUT.glob("agent-*.json")):
        d = json.loads(f.read_text())
        runs[d["model"]] = d
    return runs


# ---- tiny SVG helpers (no plotting dependency; the charts render on GitHub) -----------------------------------
def bar_chart(title: str, labels: list[str], values: list[float], unit: str, width: int = 640) -> str:
    n = len(values)
    if not n:
        return ""
    vmax = max(values) or 1
    bw, gap, left, top, h = 60, 24, 60, 40, 200
    w = max(width, left + n * (bw + gap) + 20)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h + 70}" font-family="sans-serif" font-size="12">'
    ]
    parts.append(f'<text x="{left}" y="20" font-size="14" font-weight="bold">{title}</text>')
    for i, (lab, v) in enumerate(zip(labels, values, strict=True)):
        x = left + i * (bw + gap)
        bh = int(h * v / vmax)
        parts.append(f'<rect x="{x}" y="{top + h - bh}" width="{bw}" height="{bh}" fill="#2563eb"/>')
        parts.append(f'<text x="{x + bw / 2}" y="{top + h - bh - 4}" text-anchor="middle">{v:g}{unit}</text>')
        parts.append(f'<text x="{x + bw / 2}" y="{top + h + 16}" text-anchor="middle">{lab}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def line_chart(title: str, xs: list[float], series: dict[str, list[float]], xlab: str, ylab: str) -> str:
    w, h, left, top = 640, 220, 60, 40
    allv = [v for vs in series.values() for v in vs]
    if not allv:
        return ""
    ymax = max(allv) or 1
    xmax = max(xs) or 1
    colors = ["#2563eb", "#dc2626", "#16a34a"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h + 60}" font-family="sans-serif" font-size="12">'
    ]
    parts.append(f'<text x="{left}" y="20" font-size="14" font-weight="bold">{title}</text>')
    parts.append(f'<line x1="{left}" y1="{top + h}" x2="{w - 20}" y2="{top + h}" stroke="#999"/>')
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + h}" stroke="#999"/>')
    parts.append(f'<text x="{w / 2}" y="{top + h + 40}" text-anchor="middle">{xlab}</text>')
    parts.append(
        f'<text x="14" y="{top + h / 2}" transform="rotate(-90 14 {top + h / 2})" text-anchor="middle">{ylab}</text>'
    )
    for ci, (name, vs) in enumerate(series.items()):
        pts = " ".join(
            f"{left + (w - 20 - left) * x / xmax:.1f},{top + h - h * v / ymax:.1f}"
            for x, v in zip(xs, vs, strict=True)
        )
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{colors[ci % 3]}" stroke-width="2"/>')
        for x, v in zip(xs, vs, strict=True):
            px, py = left + (w - 20 - left) * x / xmax, top + h - h * v / ymax
            parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3" fill="{colors[ci % 3]}"/>')
            parts.append(
                f'<text x="{px:.1f}" y="{py - 8:.1f}" text-anchor="middle" fill="{colors[ci % 3]}">{v:g}</text>'
            )
        parts.append(f'<text x="{w - 150}" y="{top + 16 * (ci + 1)}" fill="{colors[ci % 3]}">● {name}</text>')
    for x in xs:
        parts.append(
            f'<text x="{left + (w - 20 - left) * x / xmax:.1f}" y="{top + h + 16}" text-anchor="middle">{x:g}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    agents = latest_agent_runs()
    load = latest("load-")
    dur = latest("durability-")
    OUT.mkdir(exist_ok=True)
    md = [
        "# TripMate AI — benchmark report",
        "",
        f"_Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} by `bench/report.py` from the newest run of each benchmark in `bench/out/`. Do not edit by hand._",
        "",
    ]
    results: dict = {
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "agent": {},
        "load": None,
        "durability": None,
    }

    # ---- agent bench ----
    md += ["## 1. Agent benchmark — 20 fixed trip requests through the real graph", ""]
    md += [
        "Each scenario: one user message → intake → researcher (3 tools) → planner → budgeter (2 tools) → approval interrupt → approve → booker. Scored by **12 deterministic checks** per scenario (`bench/checks.py`): constraints extracted, reached approval, day count, dates in order, every day has an activity, activities are real sights, no sight repeated, flights match route/dates, hotel matches stay, total is consistent, budget verdict correct, booked after approval.",
        "",
    ]
    md += [
        "| model | scenarios fully passed | checks passed | p50 → proposal | p95 | LLM calls/trip | tool calls/trip | tokens in/out per trip | est. $/trip at list price | infra errors |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, d in agents.items():
        lat = d["latency_to_proposal_s"]
        md.append(
            f"| {name} | **{d['fully_passed']}/{d['completed']}** | {d['checks_passed']}/{d['checks_total']} ({100 * d['checks_passed'] / d['checks_total']:.0f} %) | {lat['p50']} s | {lat['p95']} s | {d['llm_calls_per_trip']} | {d['tool_calls_per_trip']} | {d['tokens_per_trip']['input']} / {d['tokens_per_trip']['output']} | ${d['est_cost_usd_per_trip_at_list_price']} | {len(d['infra_errors'])} |"
        )
        results["agent"][name] = {
            k: d[k]
            for k in (
                "run_id",
                "provider",
                "model",
                "tools_mode",
                "scenarios",
                "completed",
                "fully_passed",
                "checks_passed",
                "checks_total",
                "per_check_pass_rate",
                "latency_to_proposal_s",
                "llm_calls_per_trip",
                "tool_calls_per_trip",
                "tokens_per_trip",
                "est_cost_usd_per_trip_at_list_price",
            )
        }
    md.append("")
    if agents:
        names = list(agents)
        md.append(
            bar_chart(
                "p50 latency to proposal (s)",
                names,
                [agents[n]["latency_to_proposal_s"]["p50"] for n in names],
                " s",
            )
        )
        md.append("")
        md.append(
            bar_chart("scenarios fully passed (of 20)", names, [agents[n]["fully_passed"] for n in names], "")
        )
        md.append("")
        md += [
            "### Per-check pass rate",
            "",
            "| check | " + " | ".join(names) + " |",
            "|---|" + "---|" * len(names),
        ]
        for chk in next(iter(agents.values()))["per_check_pass_rate"]:
            md.append(
                f"| {chk} | "
                + " | ".join(f"{100 * agents[n]['per_check_pass_rate'][chk]:.0f} %" for n in names)
                + " |"
            )
        md.append("")
        for name, d in agents.items():
            failed = [
                (r["id"], [k for k, v in r["checks"].items() if not v])
                for r in d["rows"]
                if r["passed"] < r["of"]
            ]
            if failed:
                md += [
                    f"<details><summary>{name}: scenarios with a failed check ({len(failed)})</summary>",
                    "",
                ]
                md += [f"- `{sid}`: {', '.join(ks)}" for sid, ks in failed]
                md += ["", "</details>", ""]

    # ---- load ----
    md += ["## 2. Load benchmark — API throughput with the LLM stubbed", ""]
    if load:
        md += [
            f"k6 (`bench/load.js`) in Docker against the compose stack, `LLM_PROVIDER=fake` (scripted model, memory `{load['memory']}`). One iteration = new thread → plan (6 tool calls, 5 checkpoints) → approve (3 bookings, trip row). Fixed VUs for {load['levels'][0]['duration_s']:g} s per level.",
            "",
        ]
        md += [
            "| VUs | trips/s | req/s | p50 ms | p95 ms | plan p95 ms | approve p95 ms | errors |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for lv in load["levels"]:
            d = lv["http_req_duration_ms"]
            md.append(
                f"| {lv['vus']} | {lv['trips_per_s']} | {lv['rps']} | {d['med']} | {d['p(95)']} | {lv['plan_ms']['p(95)']} | {lv['approve_ms']['p(95)']} | {100 * lv['failed_rate']:.2f} % |"
            )
        ok = [
            lv
            for lv in load["levels"]
            if lv["http_req_duration_ms"]["p(95)"] < 500 and lv["failed_rate"] < 0.01
        ]
        best = max(ok, key=lambda lv: lv["vus"]) if ok else None  # highest concurrency still inside the SLO
        md += [
            "",
            f"**Headline:** {best['trips_per_s']} trips/s ({best['rps']} req/s) at {best['vus']} VUs with p95 {best['http_req_duration_ms']['p(95)']} ms and {100 * best['failed_rate']:.2f} % errors (SLO p95 < 500 ms, errors < 1 %)."
            if best
            else "**No level met the SLO.**",
            "",
        ]
        xs = [lv["vus"] for lv in load["levels"]]
        md.append(
            line_chart(
                "latency vs concurrency (fake LLM)",
                xs,
                {
                    "p50 ms": [lv["http_req_duration_ms"]["med"] for lv in load["levels"]],
                    "p95 ms": [lv["http_req_duration_ms"]["p(95)"] for lv in load["levels"]],
                },
                "virtual users",
                "ms",
            )
        )
        md.append("")
        md.append(
            line_chart(
                "throughput vs concurrency (fake LLM)",
                xs,
                {"trips/s": [lv["trips_per_s"] for lv in load["levels"]]},
                "virtual users",
                "trips per second",
            )
        )
        md.append("")
        results["load"] = {"run_id": load["run_id"], "levels": load["levels"], "best_within_slo": best}
    else:
        md += ["_not run yet (`make load`)_", ""]

    # ---- durability ----
    md += ["## 3. Durability — kill the API while a proposal awaits approval", ""]
    if dur:
        md += [
            f"`bench/durability.py`: {dur['reps']} × (new thread → plan → `docker compose restart api` → check the thread is still `awaiting_approval` → approve → 3 bookings + trip row).",
            "",
            f"**{dur['passed']}/{dur['reps']} passed · mean restart→healthy {dur['restart_to_healthy_s_mean']} s**",
            "",
        ]
        results["durability"] = {k: dur[k] for k in ("run_id", "reps", "passed", "restart_to_healthy_s_mean")}
    else:
        md += ["_not run yet (`make durability`)_", ""]

    # ---- what this does not prove ----
    md += [
        "## What this does NOT prove",
        "",
        "- **Bookings are simulated.** Flights/hotels come from a deterministic in-repo provider; no real inventory, no payments.",
        "- **Tools ran offline** (fixtures) in the agent benchmark, so the numbers exclude live API latency (Nominatim/Open-Meteo/Overpass) and their failure modes.",
        "- **The quality checks are structural**, not a judgment of whether the itinerary is *good*: a plan can pass all 12 checks and still be dull. There is no LLM-as-judge, on purpose.",
        "- **The load benchmark stubs the LLM.** It measures FastAPI + LangGraph + Postgres checkpointing + the tool layer on one laptop (API, Postgres and k6 share the CPU). Real throughput is bounded by the model provider's latency and rate limits, not by this service.",
        "- **One laptop, one run per level.** No warm-up separation, no repeated trials, no confidence intervals. Treat differences under ~20 % as noise.",
        "- **Free-tier model quotas** (Gemini: ~500 requests/day/model) cap how often the agent benchmark can run; the model's own non-determinism (temperature 0 is not honoured by every model) means scenario pass counts can move by ±1–2 between runs.",
        "",
    ]
    (HERE / "report.md").write_text("\n".join(md))
    (HERE / "results.json").write_text(json.dumps(results, indent=1))

    # ---- README table between markers ----
    if README.exists():
        rows = ["| what | measured | how |", "|---|---|---|"]
        for name, d in agents.items():
            lat = d["latency_to_proposal_s"]
            rows.append(
                f"| agent benchmark · {name} | **{d['fully_passed']}/{d['completed']} scenarios** fully passed, {100 * d['checks_passed'] / d['checks_total']:.0f} % of {d['checks_total']} checks · p50 {lat['p50']} s / p95 {lat['p95']} s to proposal · {d['llm_calls_per_trip']:g} LLM + {d['tool_calls_per_trip']:g} tool calls, {d['tokens_per_trip']['input']}/{d['tokens_per_trip']['output']} tokens per trip | `make bench` |"
            )
        if results["load"] and results["load"].get("best_within_slo"):
            b = results["load"]["best_within_slo"]
            rows.append(
                f"| API load (LLM stubbed) | **{b['trips_per_s']} trips/s** ({b['rps']} req/s) at {b['vus']} VUs, p95 {b['http_req_duration_ms']['p(95)']} ms, {100 * b['failed_rate']:.2f} % errors | `make load` |"
            )
        if dur:
            rows.append(
                f"| durability (restart mid-approval) | **{dur['passed']}/{dur['reps']}** resumed and booked · restart→healthy {dur['restart_to_healthy_s_mean']} s | `make durability` |"
            )
        table = (
            "\n".join(rows)
            + "\n\nFull report with charts and the list of what these numbers do **not** prove: [`bench/report.md`](bench/report.md) · raw: [`bench/results.json`](bench/results.json)."
        )
        s = README.read_text()
        s = re.sub(
            r"<!-- numbers:start -->.*?<!-- numbers:end -->",
            f"<!-- numbers:start -->\n{table}\n<!-- numbers:end -->",
            s,
            flags=re.S,
        )
        README.write_text(s)
    print(f"report → {HERE / 'report.md'} · results → {HERE / 'results.json'}")


if __name__ == "__main__":
    main()
