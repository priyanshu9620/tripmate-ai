# 01 · What it is (high-level)

**Problem.** Planning a trip is a multi-step job: understand constraints, research the place, draft days, price flights
and hotels against a budget, then commit money. One prompt to one model does this badly: it hallucinates prices, forgets
constraints, and nobody wants an LLM booking without a human saying yes.

**Solution.** A LangGraph system of specialised agents with tool calling, a human-in-the-loop pause before any booking,
and conversation memory in PostgreSQL. Served by FastAPI, containerised, deployed to AWS by GitHub Actions, traced in
LangSmith. Flights and hotels are a deterministic simulated inventory (no free real API exists) — said plainly in the README.

**Architecture in one breath.** `intake → researcher → planner → budgeter → approval → booker`. Each agent is a graph
node with its own prompt and tool set; the *supervisor* is plain code over typed state (`route()`), so routing is
unit-tested without a model. The booker is deterministic code: after a human approves, the system does exactly that.
State per thread lives in Postgres through the LangGraph checkpointer, preferences per user in the LangGraph store,
booked trips in a `trips` table. Any model via `init_chat_model`; a rule-based scripted model drives the whole graph
offline for tests and load tests.

**Numbers (measured, `bench/report.md`).** Gemini 3.5-flash-lite: 20/20 scenarios pass 12 deterministic checks each,
p50 25 s / p95 57 s to a proposal, ~6 LLM + 6 tool calls, ~6k input / 0.9k output tokens per trip (≈ $0.001 at list
price). Service with the LLM stubbed: 33 trips/s (≈100 req/s) at 20 VUs, p95 442 ms, 0 errors, one laptop. Durability:
10/10 restarts mid-approval resumed and booked. On AWS: three green CD runs, real conversations through the ALB.

**2-minute demo.** `make up && make demo`: one message → four agents stream by → proposal with total vs budget → the
API container is restarted → the pause is still there → approve → booked → a new thread already knows the preferences.
Say: "LLM proposes, code verifies, human approves, Postgres remembers."
