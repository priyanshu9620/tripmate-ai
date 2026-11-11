# 02 · Features (low-level) — what, how, where

| feature | how it is implemented | file |
|---|---|---|
| Constraint extraction | `intake` node: LLM returns one JSON object; `Constraints.merge` keeps known values, `missing()` decides whether to ask | `src/tripmate/agents/nodes.py`, `agents/state.py`, `agents/prompts.py` |
| Supervisor routing | `route(state)` maps `phase` → next node; conditional edges from every node | `agents/nodes.py`, `graph.py` |
| Tool calling with a step cap | `run_tool_loop`: model.bind_tools → tool_calls → `tool.invoke` → `ToolMessage`, max 6 rounds, usage accumulated | `agents/toolloop.py` |
| Research tools | `geocode`, `weather_forecast`, `points_of_interest`; live (Nominatim, Open-Meteo, Overpass) or fixtures; every tool returns a dict with `count/items/source` | `tools/__init__.py`, `tools/geo.py`, `weather.py`, `pois.py`, `_http.py` |
| Simulated inventory | seeded RNG from (route, date): same inputs → same 5 flights / N hotels; season multiplier; capacity fields | `providers/flights.py`, `providers/hotels.py`, `providers/catalog.py`, `fixtures/*` |
| Restart-safe bookings | ids are self-describing (`SG575-DEL-GOI-2026-12-18`); `find_flight` re-runs the search; idempotent ledger reference = sha1(item, travellers) | `providers/flights.py`, `providers/hotels.py`, `providers/bookings.py` |
| Budget fitting | budgeter: model picks ids → code re-validates against search results, capacity gate (seats/rooms), **budget guard** substitutes a fitting combo, computes total + `within_budget` | `agents/nodes.py::budgeter` |
| Human-in-the-loop | `interrupt(payload)` in `approval`; resume with `Command(resume={decision, feedback})`; reject → budgeter, max 2 | `agents/nodes.py::approval`, `api.py::approve` |
| Deterministic booker | books the 3 approved items via providers, composes the final message | `agents/nodes.py::booker` |
| Per-thread memory | `PostgresSaver` checkpointer (compiled into the graph); pending interrupt survives restart | `db.py::Memory`, `graph.py` |
| Cross-thread preferences | `PostgresStore` namespace `("prefs", user)`; loaded into intake, saved after each intake | `db.py`, `agents/nodes.py::intake` |
| Trips table | SQLAlchemy model + Alembic migration; `save_trip` idempotent per thread | `db.py`, `alembic/versions/0001_trips.py` |
| API | threads / messages / stream (SSE, one event per node) / approve / thread state / trips / healthz / metrics; `X-User` scoping; Postgres or in-memory fallback | `api.py` |
| CLI + UI | Typer `tm serve/chat/approve/trips/tools demo`; one static HTML page with approve/reject buttons | `cli.py`, `ui/index.html` |
| Provider-agnostic model | `get_model()` → `init_chat_model(model, provider)`; `fake` → `ScriptedTripModel` | `llm.py`, `fake_llm.py` |
| Scripted model | regex intake, fixed tool calls, spread planner, capacity-aware budgeter — real message shapes, no network | `fake_llm.py` |
| Metrics | Prometheus counters/histogram per turn, LLM calls, tool calls, tokens | `api.py` |
| Tracing | LangSmith via env; bench tags runs; tests never trace | `bench/run_agent.py`, `tests/conftest.py` |
| Benchmarks | 20 scenarios × 12 deterministic checks; k6 load with fake LLM; durability loop; generated report + charts | `bench/*` |
| Container + compose | uv-based Dockerfile; compose api + Postgres (host 5433); `LLM_PROVIDER` overridable | `Dockerfile`, `docker-compose.yml` |
| CI | ruff + pytest (with a Postgres service) + docker build & healthz smoke | `.github/workflows/ci.yml` |
| CD + AWS | OpenTofu: EC2 + ALB + ECR + SSM + IAM; workflow: build → ECR → SSM deploy → ALB healthy → smoke | `infra/*`, `.github/workflows/deploy.yml` |
| Portability | notes + memory in repo, `secrets.tar.enc` (AES-256) for secrets/state | `notes/`, `scripts/secrets.sh` |
