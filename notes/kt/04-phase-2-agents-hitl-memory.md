# Phase 2 — the agents, the pause, the memory (plain English)

**The shape.** `src/tripmate/graph.py` wires six nodes: intake → researcher → planner → budgeter → approval → booker.
After every node the *supervisor* decides where to go next. The supervisor is `route()` in `agents/nodes.py`: a plain
function that reads `state["phase"]`. No LLM is involved in routing — that is deliberate, so routing is tested in
milliseconds and cannot "hallucinate" a path.

**What each agent does.**
- *intake* (LLM): turns the conversation into constraints (origin, destination, date, days, travellers, budget,
  preferences). If anything is missing it asks one question and the graph ends the turn; the next message re-enters
  intake, which merges the new facts with the known ones.
- *researcher* (LLM + 3 tools): geocode, weather for the dates, all sights. Runs inside `run_tool_loop`: model →
  tool calls → results → model, at most 6 rounds. The research dict is built in code from the tool results, not from
  the model's prose, so a chatty model cannot corrupt the data.
- *planner* (LLM): JSON itinerary, N days, sights spread out, preferences favoured.
- *budgeter* (LLM + 2 tools): searches outbound + return flights and hotels, picks a combination within budget. Code
  then re-validates the ids against what the searches actually returned, computes the total itself and flags
  over-budget — the model proposes, the code verifies.
- *approval*: `interrupt(payload)`. LangGraph saves the state and stops. Resuming with `Command(resume=decision)`
  continues from exactly this line. Reject + feedback sends the graph back to the budgeter (max 2 times).
- *booker* (no LLM): books the three items in the approved proposal. Deterministic on purpose: after a human approves
  something, the system must do that thing, not re-interpret it.

**Why the pause survives a restart.** The graph is compiled with `PostgresSaver`: every node's output is a checkpoint
row in Postgres keyed by `thread_id`. A new process with the same database sees the pending interrupt and resumes.
`db.Memory` holds the saver, the `PostgresStore` (per-user preferences, used across threads) and the `trips` table.

**The scripted "fake" model.** `fake_llm.ScriptedTripModel` answers each agent's prompt with rules (regex for intake,
fixed tool calls for researcher/budgeter, a spread-out plan). It produces the same message shapes a real model would
(JSON, tool calls), so the *whole* graph runs offline in under a second. Tests, CI and the load benchmark use it; the
real model is used for the demo and the agent benchmark.

**Interview lines.** "LLM proposes, code verifies"; "routing is a pure function of typed state"; "the interrupt is a
checkpoint, so human-in-the-loop and crash-safety are the same mechanism"; "the booker is not an agent on purpose".
