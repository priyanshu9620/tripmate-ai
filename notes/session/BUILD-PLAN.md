# Build plan — TripMate AI

Order chosen so every phase is runnable, measurement comes before AWS, and the AWS stack is up for the shortest time.

## Phase 0 — Skeleton that runs  ☑ 2026-11-11 (on main, CI green)
- [x] `~/Desktop/tripmate`: `git init -b main`, per-clone identity, `.gitignore` (incl. `pre-commit-scripts/`, `post-commit-scripts/`, `.env`), `pyproject.toml` (uv, pinned), `.env.example`, `Makefile` (`up/down/test/lint/run/bench/load/demo`), README skeleton
- [x] `docker-compose.yml`: api + postgres 16; `GET /healthz` (app version + Postgres ping)
- [x] `tm` CLI + `/ui` static page echoing through a one-node graph with the fake LLM (proves wiring)
- [x] `ci.yml` (ruff + pytest + docker build); repo on GitHub, first PR
- Exit: anyone can `make up` and chat with a one-node graph at http://localhost:8000/ui; CI green.

## Phase 1 — Tools + providers (offline-first)  ☑ 2026-11-11 (on main)  (bullet 1: "tool calling")
- [x] `tools/`: `geocode`, `weather`, `pois` (live Open-Meteo / Nominatim / Overpass + recorded fixtures), `search_flights`, `search_hotels`, `book_flight`, `book_hotel` (deterministic `providers/` with CSV inventory)
- [x] `TOOLS_MODE=offline|live`; unit tests per tool on fixtures
- Exit: `make test` green with no network; `tm tools demo` prints a weather + POI + flight search for Goa.

## Phase 2 — Multi-agent graph + HITL + Postgres memory  ☑ 2026-11-11 (on main; repo still private — user flips)  (bullet 1, all three claims)
- [x] Supervisor + researcher / planner / budgeter / booker nodes (D-4), typed state, explicit routing
- [x] `interrupt()` before booker (D-6); `/approve` endpoint + `tm approve`
- [x] `PostgresSaver` + `PostgresStore` (D-7); Alembic; `trips` table; `tm trips`
- [x] SSE streaming on `/threads/{id}/messages`; `/metrics`
- [x] Routing tests with fake model; full-graph integration test on a Postgres test container
- [x] Proof: scripted conversation → interrupt → `docker compose restart api` → resume → booked
- Exit: `make demo` runs the D-13 script end to end on a clean clone; repo goes public.

## Phase 3 — Measurement  ☑ 2026-11-11 (on main f1b1994 + fix)  (adds the numbers)
- [x] `bench/scenarios.yml` (20 scenarios), `bench/run_agent.py`, deterministic quality checks (D-9a) → `results.json`
- [x] `bench/load.js` (k6 in container) with `LLM_PROVIDER=fake` (D-9b); `bench/durability.py` 10 kill-resume reps (D-9c)
- [x] `bench/report.py` → `report.md` + SVG charts; "what this does NOT prove" section; README numbers table filled from `results.json`
- [x] LangSmith run set + screenshot if key present (D-10); local JSONL run log regardless
- Exit: `make bench && make load` regenerate the report from scratch; numbers in README match `results.json`.

## Phase 4 — AWS + CD  ◐ code on main (2026-11-11); apply handed to the user  (bullet 2; the only billable phase, kept short)
- [x] `infra/` Terraform: VPC/SG, 1 × EC2 (user-data installs Docker, pulls GHCR image, compose up), ALB + target group (`/healthz`), SSM role, OIDC role for Actions, outputs (ALB DNS). Every resource block commented with what/why
- [x] `deploy.yml`: GHCR push → SSM `docker compose pull && up -d` → smoke via ALB
- [ ] User runs `terraform apply`; Claude verifies: ALB URL serves `/ui`, a real conversation reaches the interrupt and resumes; one deploy triggered by a `main` push; screenshots into `docs/`
- [ ] User runs `terraform destroy`; verify nothing billable remains
- Exit: a merged PR deployed itself to AWS and the evidence is in the repo; stack destroyed.

## Phase 5 — Interview material + resume rewrite  ☐
- [ ] `docs/GUIDE.md`, `INTERVIEW_PREP/01…06`, `DEMO.md`; `kt/` synced
- [ ] Resume lines rewritten with measured numbers (agents, tools, p50/p95 latency per plan, tokens/cost per plan, durability 10/10, load p95 at N VUs with LLM stubbed)
- Exit: user can explain every part from the repo alone.
