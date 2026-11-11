# TripMate AI — multi-agent trip planner

> A supervisor + four specialised LangGraph agents (researcher, planner, budgeter, booker) with
> tool calling, a human-in-the-loop approval pause before any booking, and conversation memory in PostgreSQL —
> served by FastAPI, containerised with Docker, deployed to AWS by GitHub Actions. Bookings are simulated.

## How it works

```
                 ┌────────── supervisor: route(state) — plain code, no LLM ──────────┐
 user message ─► intake ─► researcher ─► planner ─► budgeter ─► approval ─► booker ─► trip saved
                 (LLM:     (LLM + tools: (LLM)      (LLM + tools:  interrupt()  (code: books
                 extract    geocode,                 search_flights, ⏸ waits for   exactly what
                 constraints weather,                search_hotels)  approve /     was approved)
                 or ask)    sights)                                  reject)
                 ▲                                                   │
                 └──────── reject + feedback → budgeter again ◄──────┘

 state per thread → Postgres (LangGraph checkpointer)   preferences per user → Postgres (LangGraph store)
 booked trips → `trips` table (SQLAlchemy + Alembic)    served by FastAPI (+ SSE stream) · CLI `tm` · /ui page
```

- **Agents** (`src/tripmate/agents/`): each is a node with its own prompt and tool set; the supervisor is a pure
  function of the typed state, so routing is unit-tested without a model.
- **Human-in-the-loop**: `interrupt()` before the booker; a message while a proposal is pending counts as a rejection
  with feedback; after two rejections the agent stops.
- **Memory**: `PostgresSaver` (per-thread state, survives restarts) + `PostgresStore` (cross-thread preferences).
- **Any model**: `LLM_PROVIDER` / `LLM_MODEL` in `.env` (Gemini, Anthropic, Groq, Ollama via `init_chat_model`);
  `fake` is a rule-based scripted model that drives the whole graph deterministically for tests and load tests.

## Run it

```
cp .env.example .env     # optional: add a model key; without one the fake echo model is used
make up                  # api + postgres → http://localhost:8000/ui
make chat                # terminal chat (y approves a pending proposal; any other text = feedback)
make demo                # 2-minute scripted demo incl. a restart mid-approval (DEMO.md)
make test                # offline tests, no network (Postgres test runs if localhost:5433 is up)
```

API: `POST /threads` · `POST /threads/{id}/messages` · `POST /threads/{id}/stream` (SSE) · `POST /threads/{id}/approve` ·
`GET /threads/{id}` · `GET /trips` · `GET /healthz` · `GET /metrics`. Header `X-User` scopes preferences and trips.

## Tools (Phase 1)
Seven LangChain tools in `src/tripmate/tools/`: `geocode`, `weather_forecast`, `points_of_interest` (live via
Nominatim / Open-Meteo / Overpass when `TOOLS_MODE=live`, curated fixtures otherwise, with automatic fallback),
`search_flights`, `search_hotels` (simulated, deterministic inventory in `providers/`), and the two mutating tools
`book_flight`, `book_hotel` (idempotent, in-process ledger). `uv run tm tools demo --destination Goa` shows them.

## Measured numbers

<!-- numbers:start -->
| what | measured | how |
|---|---|---|
| agent benchmark · scripted | **20/20 scenarios** fully passed, 100 % of 240 checks · p50 0.01 s / p95 0.08 s to proposal · 6 LLM + 6 tool calls, 1292/227 tokens per trip | `make bench` |
| agent benchmark · gemini-3.5-flash-lite | **20/20 scenarios** fully passed, 100 % of 240 checks · p50 25.22 s / p95 56.77 s to proposal · 6.25 LLM + 6.1 tool calls, 5986/912 tokens per trip | `make bench` |
| API load (LLM stubbed) | **33.3 trips/s** (99.9 req/s) at 20 VUs, p95 441.6 ms, 0.00 % errors | `make load` |
| durability (restart mid-approval) | **10/10** resumed and booked · restart→healthy 1.03 s | `make durability` |

Full report with charts and the list of what these numbers do **not** prove: [`bench/report.md`](bench/report.md) · raw: [`bench/results.json`](bench/results.json).
<!-- numbers:end -->

## Project notes, memory and secrets
Everything needed to continue on another machine is in this repo: [`notes/`](notes/) (decisions, build plan, progress, problems, KT),
[`notes/claude-memory/`](notes/claude-memory/) and `secrets.tar.enc` (one passphrase). Start at [`notes/BOOTSTRAP.md`](notes/BOOTSTRAP.md).

## Docs
[`docs/GUIDE.md`](docs/GUIDE.md) (the manual) · [`docs/RUNBOOK.md`](docs/RUNBOOK.md) (bring AWS up before a demo, down after) · [`DEMO.md`](DEMO.md) · [`docs/aws-evidence.md`](docs/aws-evidence.md) · [`INTERVIEW_PREP/`](INTERVIEW_PREP/) · [`bench/report.md`](bench/report.md)

## Roadmap
0 skeleton ✔ · 1 tools ✔ · 2 multi-agent graph + HITL + Postgres memory ✔ · 3 measurement ✔ · 4 AWS + CD ✔ · 5 interview material ✔ · next: real inventory sandbox, multi-worker serving, LLM-judge quality score
