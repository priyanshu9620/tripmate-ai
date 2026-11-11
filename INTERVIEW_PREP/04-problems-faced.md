# 04 · Problems faced — symptom → cause → fix → lesson

Every entry below is a real error from building this (source of truth: `notes/session/PROBLEMS.md`). Told as stories so they come out naturally in an interview.

## P-1 — Creating a *public* GitHub repo was denied by the Claude Code permission classifier
("Create Public Surface"). Not a code problem. Fix: created it private (`gh repo create --private`); D-16 wanted it public only after Phase 2 anyway, so the user flips visibility then (repo Settings → Danger zone → Change visibility, or `gh repo edit --visibility public`). Lesson: anything that publishes needs the human; plan the visibility flip as a user step.

## P-2 — Overpass (OpenStreetMap POI API) times out on every public mirror
(`overpass-api.de`, `kumi.systems`, `private.coffee`: ReadTimeout at 20–25 s even for a nodes-only 10 km query), while Nominatim and Open-Meteo answer in <1 s from the same network. Not fixed — by design the tool returns the curated fixture list with `source: fixture` when the live call fails, and the demo showed exactly that. Lesson: every live downstream on an agent's path needs a bounded timeout and a usable fallback *before* you depend on it; the agent must never block on a flaky free API. Query kept small (nodes only) so it succeeds when the servers are healthy.

## P-3 — CI red on the Phase 1 commit: one ruff E501
Cause: my commit command ran `ruff check … >/dev/null && …` — the lint failure was silenced and the commit went ahead. Fix: wrapped the line; commit pushed 10 min later. Lesson: the gate must be visible and must stop the pipeline — never redirect a check's output to `/dev/null` in the same command that commits; CI caught it, which is exactly why CI exists.

## P-4 — Container silently ran with in-memory state although Postgres was healthy
`/healthz` said `memory: "memory"`. Cause: the Dockerfile copied `src/` but not `alembic/` + `alembic.ini`, so `Memory.setup()` → `migrate()` raised "Path doesn't exist: /app/alembic" and the lifespan fell back to `InMemorySaver`. The fallback is right for tests but it hid a packaging bug. Fix: copy the migration folder; `/healthz` now exposes `memory` so the demo/bench can assert `postgres`. Lesson: a graceful fallback needs a loud signal (log + health field) or it becomes a silent downgrade in production.

## P-5 — Gemini: `ValueError: contents are required` in the researcher
The researcher/planner/budgeter were invoked with a system prompt only (`[SystemMessage]`); the scripted fake didn't care, Gemini refuses. Fix: every agent call carries a short human turn ("Research this trip now."), and `run_tool_loop` adds one if the history is empty. Lesson: the fake model proves the graph logic, not provider contracts — always run one real-model pass before calling a phase done (same lesson as Pager-Zero P-24).

## P-6 — Twice committed with a ruff error because the shell chain continued after the failed check
(`check >/dev/null && …` once; `check; echo ok` once — and `cmd | tail` masks exit codes). Fix: a single `&&` chain with no redirects/pipes on the gate, and `scripts/` is now linted in CI. Lesson: the gate must be the thing that can stop the commit; CI is the backstop, not the gate.

## P-7 — Researcher filtered sights to the user's preference kind → planner had 2 beaches for 4 days
(Gemini run 1: "Baga Beach" on 3 of 4 days). Cause: the researcher prompt said to pass preferences as `kinds`. Fix: researcher fetches all sights (limit 12) and the planner applies preferences ("favour", "each sight at most once"). Run 2 gave a varied 4-day plan. Lesson: filter at the decision point, not at the data source.

## P-8 — Flight `total_inr` ≠ `price_per_person × passengers` by ₹10
(separate rounding). The model's reasoning summed per-person prices and disagreed with our total by ₹10. Fix: total derived from the rounded per-person price. Lesson: expose one number and derive the rest; never round twice.

## P-9 — Groups of 3+ could not book (scripted bench run 1: 4/20 scenarios)
The budgeter picked the cheapest flight/hotel without checking `seats_left` / `rooms_left`; the booker then failed "only N seats left". Fix: capacity gate in `nodes.py` (candidates filtered by party size before the model's pick is accepted, fallback = cheapest *with* capacity), the prompt says so, the scripted model does the same; regression test with 6 travellers. Lesson: the benchmark found a real product bug before any real model ran — run the cheap baseline first.

## P-10 — `LLM_PROVIDER=fake docker compose up` did not reach the container
(healthz still said google_genai; load bench aborted). `env_file: .env` sets the variable and a shell variable only affects compose *interpolation*. Fix: `LLM_PROVIDER: ${LLM_PROVIDER:-google_genai}` under `environment:` (shell wins over `.env` for interpolation). Lesson: with env_file, nothing from the shell reaches the container unless you interpolate it explicitly — assert via `/healthz`, as the load script now does.

## P-11 — LangSmith free tier: "Monthly unique traces usage limit exceeded" (HTTP 429) during the 20-scenario bench
Each graph node/tool is a span and every pytest run had been tracing too (the `.env` is loaded by `config.py`). Fix: `LANGSMITH_TRACING=false` in `tests/conftest.py`; tracing is now spent only on demos and the bench. Some bench traces were dropped (the bench itself is unaffected — tracing is fire-and-forget). Lesson: tracing has a budget; exclude tests and CI from it on day one.

## P-12 — Several "applied" code edits had silently missed
(string-replace anchors no longer matched after `ruff format` reflowed the target; the script went on without asserting). The P-7 researcher fix and its test were among them — found only when the bench showed 2 sights for 4 days. Fix: every edit now asserts its anchor and is verified with `grep` before the test run. Lesson: an edit you did not verify is an edit you did not make.

## P-13 — Same-airport pair in a scenario
(Dehradun→Rishikesh both DED): ids became `…-DED-DED-…`, booking failed. Fix: `search_flights` returns nothing when the airports match; scenario moved to Delhi→Rishikesh. Lesson: scenario data needs the same review as code.

## P-14 — First agent turn on AWS returned an empty body after 61 s
although `/approve` then worked and the trip was saved. Cause: ALB default idle timeout = 60 s; with `TOOLS_MODE=live` (Overpass times out at 8 s before falling back) plus Gemini the turn exceeded it, so the ALB dropped the response while the graph finished. Fix: `idle_timeout = 300` on the ALB (apply pending). Lesson: every hop between the user and a long-running agent call has a timeout; list them (ALB 60 s, uvicorn, httpx, tool timeouts) before the first deploy — or stream (the `/stream` SSE endpoint keeps the connection alive per node).

## P-15 — Deploy workflow smoke step failed: `AccessDenied` on `elasticloadbalancing:DescribeLoadBalancers`
for the scoped deploy user (the deploy itself had succeeded). Fix: action added to the policy. Lesson: a scoped IAM policy must be exercised end-to-end once; the ShopEase policy I copied never needed that call.

## P-16 — Gemini proposed over budget on AWS (premium hotel, ₹47,260 vs ₹45,000) although cheaper hotels were in its own search results
The same scenario had passed in the bench — model non-determinism. The code flagged OVER BUDGET (by design) but a user would rightly ask why it didn't just pick a cheaper hotel. Fix: budget guard in the budgeter — when the pick is over budget and a fitting combination exists, substitute cheapest flights + best-rated fitting hotel and say so in `reasoning`; regression test with a model that deliberately picks premium. Lesson: "LLM proposes, code verifies" should include "code repairs when the fix is unambiguous"; flagging is not enough when the user's constraint is hard.

## The three I'd lead with

1. **P-14, the ALB cut a 61-second agent turn.** The server finished the work; the user saw nothing. Every hop between a user and a long-running agent has a timeout — list them before the first deploy, and stream.
2. **P-9, groups could not book.** The cheapest flight had 2 seats for a party of 6. Found by the scripted benchmark before any real model ran — the benchmark is a bug-finder, not a scoreboard.
3. **P-16, the model proposed over budget in production** for a scenario that had passed in the bench. Flagging was not enough; the code now repairs it. Models drift; constraints must be code.
