# 03 · How it works — the concepts, why they are needed, trade-offs

**LangGraph state graph.** A graph of nodes over a typed state with reducers (`messages` appends, `research` merges,
`usage` sums). Why: explicit control flow + persistence; a free-form "agents chat" loop is untestable and unbounded.
Trade-off: more code than one ReAct agent; routing logic lives in prompts *and* code — we chose code.

**Supervisor as pure code.** `route()` reads `phase`. Why: deterministic, millisecond tests, no routing hallucination.
Trade-off: the supervisor cannot "decide creatively" — fine, the creativity sits inside the agents.

**Tool calling.** The model emits structured `tool_calls`; the runtime executes functions and feeds `ToolMessage`s
back. Why: grounded facts (weather, prices) instead of invented ones. Design rules learned the hard way: every tool
returns a dict (some providers reject empty lists), a step cap (6), bounded timeouts with a fallback for live calls.

**"LLM proposes, code verifies (and repairs)".** The budgeter's picks are re-validated against what the searches
returned, filtered for capacity, and replaced by a fitting combination if over budget. Why: hard constraints must be
enforced by code; models drift between runs (same scenario passed in the bench, failed in production).

**Human-in-the-loop with `interrupt()`.** The graph raises an interrupt; the runtime checkpoints and returns; `Command
(resume=…)` continues from that point. Why: irreversible actions need consent. Key insight: the interrupt *is* a
checkpoint, so crash-safety and HITL are one mechanism — proven by killing the API 10/10 times mid-approval.

**Checkpointer vs store.** Checkpointer = per-thread state history (every node output). Store = key/value across
threads (user preferences). Both Postgres. Trade-off: a checkpoint per node costs a round trip (visible in the load
test as the plateau at ≈33 trips/s on one worker).

**Deterministic simulation.** Flights/hotels are pure functions of (route, date) with seeded randomness. Why: reproducible
evals and demos; no API key or cost. Trade-off: not real inventory — stated in README and report.

**Scripted fake model.** A rule-based model that answers each agent prompt with the right shape. Why: tests/CI in
seconds, a load test that measures *our* service, a 20/20 baseline that proves the checks before a real model runs.

**Deterministic evaluation (no LLM judge).** 12 structural checks per scenario. Why: comparable across runs, failures
name a field. Limitation: structural, not "is the plan delightful".

**SSE streaming.** `graph.stream(stream_mode="updates")` → one event per node. Why: feedback during 25–60 s turns and
it keeps proxies' idle timeouts from cutting the response (the ALB did, at 60 s).

**Infra as code + CD.** OpenTofu for everything; GitHub Actions builds amd64 image → ECR → SSM Run Command → ALB health
→ smoke. Why: reproducible, teardown in one command, and a scoped IAM identity (OIDC was denied by the account policy).
