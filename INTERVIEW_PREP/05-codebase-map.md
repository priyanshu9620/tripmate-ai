# 05 · Codebase map — and where to add a new X

```
src/tripmate/
  config.py        Settings (.env → object + os.environ)         llm.py        get_model(): provider switch, fake/echo
  graph.py         build_graph(): nodes, edges, checkpointer      fake_llm.py   ScriptedTripModel (rule-based, per agent)
  agents/          state.py (TripState, Constraints) · prompts.py · toolloop.py (bounded loop) · nodes.py (6 nodes + route)
  tools/           __init__.py (7 @tool wrappers, groups) · geo.py · weather.py · pois.py · _http.py (timeouts, live flag)
  providers/       catalog.py (fixtures, resolve_place) · flights.py · hotels.py · bookings.py (idempotent ledger)
  fixtures/        destinations.json (18 places, climate normals, 16 sights each) · airlines.csv · hotels.csv (90)
  db.py            Memory: pool, PostgresSaver, PostgresStore, Trip model, migrate()
  api.py           FastAPI routes + metrics       cli.py  Typer `tm`       ui/index.html  chat page
  jsonutil.py      extract_json()
alembic/           migrations (0001_trips)        tests/   25 tests (graph, api, tools, providers, postgres)
bench/             scenarios.yml · checks.py · run_agent.py · run_load.py + load.js · durability.py · report.py · out/
scripts/           demo.py · secrets.sh           infra/   OpenTofu (main/variables/outputs, user-data.sh)
.github/workflows/ ci.yml · deploy.yml            docs/    GUIDE.md · aws-evidence.md      notes/  project memory
```

**Add a tool.** Write the function in `tools/<x>.py` (offline + live paths, fixture fallback), wrap it with `@tool` in
`tools/__init__.py` returning a dict, add it to the right group (`RESEARCH_TOOLS` / `BUDGET_TOOLS` / `BOOKING_TOOLS`),
mention it in the agent's prompt, teach `fake_llm` to call it, add a fixture-based test.

**Add an agent.** A method on `Nodes` that returns a partial state incl. `phase`; register in `graph.py`; add the phase
to `route()`; add a `_<name>` handler in `ScriptedTripModel` keyed by the `AGENT:` tag; a routing test.

**Add a destination.** One entry in `fixtures/destinations.json` (geo, airport, 12 monthly climate rows, 16 sights) +
hotel rows in `hotels.csv`; everything else derives from it.

**Add a model provider.** Nothing in code if LangChain supports it: set `LLM_PROVIDER`/`LLM_MODEL`/key in `.env`; pin
the `langchain-<provider>` package in `pyproject.toml` if missing.

**Add a benchmark check.** One key in `bench/checks.py::check`; it appears automatically in the report's per-check table.

**Add a metric.** A `prometheus_client` counter/histogram in `api.py`; scrape `/metrics`.

**Add a deployable change.** `infra/main.tf` with a what/why comment → `make infra-plan` → user applies.
