# TripMate AI — benchmark report

_Generated 2026-11-11 13:11 UTC by `bench/report.py` from the newest run of each benchmark in `bench/out/`. Do not edit by hand._

## 1. Agent benchmark — 20 fixed trip requests through the real graph

Each scenario: one user message → intake → researcher (3 tools) → planner → budgeter (2 tools) → approval interrupt → approve → booker. Scored by **12 deterministic checks** per scenario (`bench/checks.py`): constraints extracted, reached approval, day count, dates in order, every day has an activity, activities are real sights, no sight repeated, flights match route/dates, hotel matches stay, total is consistent, budget verdict correct, booked after approval.

| model | scenarios fully passed | checks passed | p50 → proposal | p95 | LLM calls/trip | tool calls/trip | tokens in/out per trip | est. $/trip at list price | infra errors |
|---|---|---|---|---|---|---|---|---|---|
| scripted | **20/20** | 240/240 (100 %) | 0.01 s | 0.08 s | 6.0 | 6.0 | 1292 / 227 | $0.0 | 0 |
| gemini-3.5-flash-lite | **20/20** | 240/240 (100 %) | 25.22 s | 56.77 s | 6.25 | 6.1 | 5986 / 912 | $0.00096 | 0 |

<svg xmlns="http://www.w3.org/2000/svg" width="640" height="270" font-family="sans-serif" font-size="12">
<text x="60" y="20" font-size="14" font-weight="bold">p50 latency to proposal (s)</text>
<rect x="60" y="240" width="60" height="0" fill="#2563eb"/>
<text x="90.0" y="236" text-anchor="middle">0.01 s</text>
<text x="90.0" y="256" text-anchor="middle">scripted</text>
<rect x="144" y="40" width="60" height="200" fill="#2563eb"/>
<text x="174.0" y="36" text-anchor="middle">25.22 s</text>
<text x="174.0" y="256" text-anchor="middle">gemini-3.5-flash-lite</text>
</svg>

<svg xmlns="http://www.w3.org/2000/svg" width="640" height="270" font-family="sans-serif" font-size="12">
<text x="60" y="20" font-size="14" font-weight="bold">scenarios fully passed (of 20)</text>
<rect x="60" y="40" width="60" height="200" fill="#2563eb"/>
<text x="90.0" y="36" text-anchor="middle">20</text>
<text x="90.0" y="256" text-anchor="middle">scripted</text>
<rect x="144" y="40" width="60" height="200" fill="#2563eb"/>
<text x="174.0" y="36" text-anchor="middle">20</text>
<text x="174.0" y="256" text-anchor="middle">gemini-3.5-flash-lite</text>
</svg>

### Per-check pass rate

| check | scripted | gemini-3.5-flash-lite |
|---|---|---|
| constraints_extracted | 100 % | 100 % |
| reached_approval | 100 % | 100 % |
| day_count | 100 % | 100 % |
| dates_in_order | 100 % | 100 % |
| every_day_has_activity | 100 % | 100 % |
| activities_are_real_sights | 100 % | 100 % |
| no_sight_repeated | 100 % | 100 % |
| flights_match_route_and_dates | 100 % | 100 % |
| hotel_matches_stay | 100 % | 100 % |
| total_is_consistent | 100 % | 100 % |
| budget_verdict_correct | 100 % | 100 % |
| booked_after_approval | 100 % | 100 % |

## 2. Load benchmark — API throughput with the LLM stubbed

k6 (`bench/load.js`) in Docker against the compose stack, `LLM_PROVIDER=fake` (scripted model, memory `postgres`). One iteration = new thread → plan (6 tool calls, 5 checkpoints) → approve (3 bookings, trip row). Fixed VUs for 30 s per level.

| VUs | trips/s | req/s | p50 ms | p95 ms | plan p95 ms | approve p95 ms | errors |
|---|---|---|---|---|---|---|---|
| 2 | 37.53 | 112.6 | 17.1 | 36.1 | None | None | 0.00 % |
| 5 | 34.2 | 102.6 | 56.1 | 99.5 | None | None | 0.00 % |
| 10 | 33.2 | 99.6 | 111.9 | 214.2 | None | None | 0.00 % |
| 20 | 33.3 | 99.9 | 211.9 | 441.6 | None | None | 0.00 % |

**Headline:** 33.3 trips/s (99.9 req/s) at 20 VUs with p95 441.6 ms and 0.00 % errors (SLO p95 < 500 ms, errors < 1 %).

<svg xmlns="http://www.w3.org/2000/svg" width="640" height="280" font-family="sans-serif" font-size="12">
<text x="60" y="20" font-size="14" font-weight="bold">latency vs concurrency (fake LLM)</text>
<line x1="60" y1="260" x2="620" y2="260" stroke="#999"/>
<line x1="60" y1="40" x2="60" y2="260" stroke="#999"/>
<text x="320.0" y="300" text-anchor="middle">virtual users</text>
<text x="14" y="150.0" transform="rotate(-90 14 150.0)" text-anchor="middle">ms</text>
<polyline points="116.0,251.5 200.0,232.1 340.0,204.3 620.0,154.4" fill="none" stroke="#2563eb" stroke-width="2"/>
<circle cx="116.0" cy="251.5" r="3" fill="#2563eb"/>
<text x="116.0" y="243.5" text-anchor="middle" fill="#2563eb">17.1</text>
<circle cx="200.0" cy="232.1" r="3" fill="#2563eb"/>
<text x="200.0" y="224.1" text-anchor="middle" fill="#2563eb">56.1</text>
<circle cx="340.0" cy="204.3" r="3" fill="#2563eb"/>
<text x="340.0" y="196.3" text-anchor="middle" fill="#2563eb">111.9</text>
<circle cx="620.0" cy="154.4" r="3" fill="#2563eb"/>
<text x="620.0" y="146.4" text-anchor="middle" fill="#2563eb">211.9</text>
<text x="490" y="56" fill="#2563eb">● p50 ms</text>
<polyline points="116.0,242.0 200.0,210.4 340.0,153.3 620.0,40.0" fill="none" stroke="#dc2626" stroke-width="2"/>
<circle cx="116.0" cy="242.0" r="3" fill="#dc2626"/>
<text x="116.0" y="234.0" text-anchor="middle" fill="#dc2626">36.1</text>
<circle cx="200.0" cy="210.4" r="3" fill="#dc2626"/>
<text x="200.0" y="202.4" text-anchor="middle" fill="#dc2626">99.5</text>
<circle cx="340.0" cy="153.3" r="3" fill="#dc2626"/>
<text x="340.0" y="145.3" text-anchor="middle" fill="#dc2626">214.2</text>
<circle cx="620.0" cy="40.0" r="3" fill="#dc2626"/>
<text x="620.0" y="32.0" text-anchor="middle" fill="#dc2626">441.6</text>
<text x="490" y="72" fill="#dc2626">● p95 ms</text>
<text x="116.0" y="276" text-anchor="middle">2</text>
<text x="200.0" y="276" text-anchor="middle">5</text>
<text x="340.0" y="276" text-anchor="middle">10</text>
<text x="620.0" y="276" text-anchor="middle">20</text>
</svg>

<svg xmlns="http://www.w3.org/2000/svg" width="640" height="280" font-family="sans-serif" font-size="12">
<text x="60" y="20" font-size="14" font-weight="bold">throughput vs concurrency (fake LLM)</text>
<line x1="60" y1="260" x2="620" y2="260" stroke="#999"/>
<line x1="60" y1="40" x2="60" y2="260" stroke="#999"/>
<text x="320.0" y="300" text-anchor="middle">virtual users</text>
<text x="14" y="150.0" transform="rotate(-90 14 150.0)" text-anchor="middle">trips per second</text>
<polyline points="116.0,40.0 200.0,59.5 340.0,65.4 620.0,64.8" fill="none" stroke="#2563eb" stroke-width="2"/>
<circle cx="116.0" cy="40.0" r="3" fill="#2563eb"/>
<text x="116.0" y="32.0" text-anchor="middle" fill="#2563eb">37.53</text>
<circle cx="200.0" cy="59.5" r="3" fill="#2563eb"/>
<text x="200.0" y="51.5" text-anchor="middle" fill="#2563eb">34.2</text>
<circle cx="340.0" cy="65.4" r="3" fill="#2563eb"/>
<text x="340.0" y="57.4" text-anchor="middle" fill="#2563eb">33.2</text>
<circle cx="620.0" cy="64.8" r="3" fill="#2563eb"/>
<text x="620.0" y="56.8" text-anchor="middle" fill="#2563eb">33.3</text>
<text x="490" y="56" fill="#2563eb">● trips/s</text>
<text x="116.0" y="276" text-anchor="middle">2</text>
<text x="200.0" y="276" text-anchor="middle">5</text>
<text x="340.0" y="276" text-anchor="middle">10</text>
<text x="620.0" y="276" text-anchor="middle">20</text>
</svg>

## 3. Durability — kill the API while a proposal awaits approval

`bench/durability.py`: 10 × (new thread → plan → `docker compose restart api` → check the thread is still `awaiting_approval` → approve → 3 bookings + trip row).

**10/10 passed · mean restart→healthy 1.03 s**

## What this does NOT prove

- **Bookings are simulated.** Flights/hotels come from a deterministic in-repo provider; no real inventory, no payments.
- **Tools ran offline** (fixtures) in the agent benchmark, so the numbers exclude live API latency (Nominatim/Open-Meteo/Overpass) and their failure modes.
- **The quality checks are structural**, not a judgment of whether the itinerary is *good*: a plan can pass all 12 checks and still be dull. There is no LLM-as-judge, on purpose.
- **The load benchmark stubs the LLM.** It measures FastAPI + LangGraph + Postgres checkpointing + the tool layer on one laptop (API, Postgres and k6 share the CPU). Real throughput is bounded by the model provider's latency and rate limits, not by this service.
- **One laptop, one run per level.** No warm-up separation, no repeated trials, no confidence intervals. Treat differences under ~20 % as noise.
- **Free-tier model quotas** (Gemini: ~500 requests/day/model) cap how often the agent benchmark can run; the model's own non-determinism (temperature 0 is not honoured by every model) means scenario pass counts can move by ±1–2 between runs.
