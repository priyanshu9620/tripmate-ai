# TripMate AI — the manual

Self-contained: every command, every surface, troubleshooting. No chat history needed. See also
[`notes/BOOTSTRAP.md`](../notes/BOOTSTRAP.md) for a fresh laptop and [`DEMO.md`](../DEMO.md) for the 2-minute demo.

## 1. Prerequisites
Docker (Desktop on macOS), `uv`, Python 3.11 (`uv python install 3.11`), optionally `tofu` + `aws` CLI for AWS,
`gh` for GitHub. A model key in `.env` (Gemini free tier works; see `.env.example`), or `LLM_PROVIDER=fake`.

## 2. Configuration (`.env`, git-ignored; template `.env.example`)
| key | meaning | default |
|---|---|---|
| `LLM_PROVIDER` | `google_genai` · `anthropic` · `groq` · `ollama` · `fake` (scripted, no key) · `echo` | `fake` in code, `google_genai` in `.env.example` |
| `LLM_MODEL` | model id for the provider | `gemini-3.5-flash-lite` |
| `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY` / `GROQ_API_KEY` | provider key | — |
| `DATABASE_URL` | Postgres; the API falls back to in-memory state if unreachable (health shows `memory: memory`) | `postgresql://tm:tm@localhost:5433/tripmate` |
| `TOOLS_MODE` | `offline` (fixtures) · `live` (Nominatim / Open-Meteo / Overpass, fixture fallback) | `offline` |
| `TOOLS_TIMEOUT_S` | per live call | `8` |
| `LANGSMITH_TRACING` / `LANGSMITH_API_KEY` / `LANGSMITH_PROJECT` | tracing (optional) | off |
| `HOST` / `PORT` | bind address for `tm serve` | `127.0.0.1:8000` |

Switching model = editing `.env`, no code change. Unit tests force `LLM_PROVIDER=fake` and tracing off.

## 3. Commands (Makefile)
| command | what |
|---|---|
| `make up` / `make down` / `make logs` | compose stack: api (`:8000`) + Postgres 16 (`:5433` on the host) |
| `LLM_PROVIDER=fake make up` | same stack with the scripted model (load bench, offline demos) |
| `make run` | API from the venv (needs Postgres from `make up` or in-memory fallback) |
| `make chat` | terminal chat; `y` approves a pending proposal, any other text is feedback; `--thread <id>` resumes |
| `uv run tm approve <thread> [--reject --feedback "..."]` · `uv run tm trips` | approve/reject · list booked trips |
| `uv run tm tools demo --destination Goa --origin Delhi` | run the read tools without an LLM |
| `make demo` | scripted 2-minute demo incl. an API restart mid-approval (needs `make up`) |
| `make test` / `make lint` / `make fmt` | 25 tests (Postgres test skipped if `:5433` is down) · ruff |
| `make migrate` | Alembic `upgrade head` (the API also migrates at startup) |
| `make bench` / `make bench-fake` | 20-scenario agent benchmark with the real / scripted model |
| `make load` | k6 (Docker) at 2/5/10/20 VUs; API must run with `LLM_PROVIDER=fake` |
| `make durability` | 10 × restart the API mid-approval and resume |
| `make report` | regenerate `bench/report.md`, charts, `bench/results.json`, README numbers |
| `make infra-plan` / `infra-apply` / `infra-destroy` / `infra-output` | AWS stack (OpenTofu); apply/destroy are billable |
| `make secrets-pack` / `secrets-unpack` | encrypted archive of `.env`, tfvars, tfstate, AWS profile (`SECRETS_PASSPHRASE`) |

## 4. HTTP API (`http://localhost:8000`, header `X-User` scopes preferences + trips, default `demo`)
| endpoint | body → result |
|---|---|
| `POST /threads` | → `{thread_id}` |
| `POST /threads/{id}/messages` | `{content}` → `{status: awaiting_input│awaiting_approval│done, reply, proposal?, itinerary?, trip?, usage}`; a message while a proposal is pending = reject with that feedback |
| `POST /threads/{id}/stream` | same input; SSE: one `node` event per agent step, then `final` |
| `POST /threads/{id}/approve` | `{decision: approve│reject, feedback?}` → same as above; 409 if nothing is pending |
| `GET /threads/{id}` | status, phase, constraints, proposal, itinerary, bookings, usage, messages; 404 if unknown |
| `GET /trips` | booked trips for `X-User` |
| `GET /healthz` | version, llm_provider, tools_mode, memory (`postgres`│`memory`), postgres ping |
| `GET /metrics` | Prometheus: `tripmate_turns_total{status}`, `tripmate_turn_seconds`, `tripmate_llm_calls_total`, `tripmate_tool_calls_total`, `tripmate_tokens_total{direction}` |
| `GET /ui` | chat page; `?thread=<id>` reloads a thread, `&user=<name>` sets `X-User` |

## 5. The conversation, step by step
1. `intake` extracts origin, destination, ISO start date, days, travellers, budget (INR, whole trip), preferences. Missing fields → one question, turn ends (`awaiting_input`). Known destinations: goa, jaipur, manali, kochi, udaipur, rishikesh, bali, dubai, singapore, bangkok (+ origins delhi, mumbai, bengaluru, hyderabad, kolkata, chennai, pune, dehradun).
2. `researcher` calls `geocode`, `weather_forecast`, `points_of_interest` (≤ 6 rounds).
3. `planner` returns a JSON itinerary with `days` days.
4. `budgeter` searches flights both ways and hotels, picks a combination; code re-validates ids, applies the capacity gate (seats/rooms) and the budget guard, computes the total → `awaiting_approval`.
5. `approval`: `interrupt()`; `approve` → `booker` books the 3 items and saves the trip (`done`); `reject` (+feedback) → budgeter again, max 2 times.

## 6. Troubleshooting
| symptom | cause / fix |
|---|---|
| `/healthz` shows `memory: memory` | Postgres unreachable or migrations missing → `make up`; check `docker compose logs api` for "postgres memory unavailable" |
| `ValueError: contents are required` | a provider got a system-only prompt; every agent call now includes a human turn — update if you add an agent |
| 429 / `RESOURCE_EXHAUSTED` from Gemini | free quota ≈ 500 requests/day/model; one trip ≈ 6–7 requests; the bench ≈ 130; wait for the reset (~13:30 IST) or switch provider |
| LangSmith 429 "usage limit" | free tier monthly trace cap; tracing is fire-and-forget, the app is unaffected; tests never trace |
| `points_of_interest` says `source: fixture` in live mode | Overpass timed out (common); the fixture fallback is by design |
| booking fails "unknown flight_id" | the id was not produced by `search_flights` for that route/date; ids are self-describing (`CODE123-DEL-GOI-YYYY-MM-DD`) |
| Response empty after ~60 s behind a proxy/ALB | idle timeout; the ALB is set to 300 s in `infra/`; or use `/stream` |
| `make load` aborts "needs fake" | start the API with `LLM_PROVIDER=fake make up` |
| `tofu init` hangs | GitHub release assets unreachable on some networks; `~/.tofurc` points at a local provider mirror (see ShopEase notes) |
| `git push` rejected (work account) | use the personal token: `git -c credential.helper= -c "http.https://github.com/.extraheader=AUTHORIZATION: basic $(printf 'x-access-token:%s' "$(gh auth token --user priyanshu9620)" | base64)" push` |

## 7. AWS in one screen
`infra/` = default VPC, 2 SGs, ECR, 7 SSM params, instance role, 1 × t3.micro (compose: api + Postgres), ALB (idle 300 s),
scoped deploy IAM user. `make infra-apply` → `gh secret set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY` from `tofu output`,
`gh variable set AWS_DEPLOY_ENABLED true` → every push to `main` builds, pushes to ECR, deploys via SSM, waits for the ALB,
smoke-tests `/healthz`. Set the variable to `false` before `make infra-destroy`. Cost ≈ $1/day while up. Evidence of the
real run: [`aws-evidence.md`](aws-evidence.md).
