# Phase 3 — how the numbers are made (plain English)

**Rule.** Nothing on the resume is typed in. `make bench`, `make load`, `make durability` write JSON into `bench/out/`;
`make report` turns the newest of each into `bench/report.md` (with charts), `bench/results.json`, and the table in
the README. If a number is wrong, the fix is a script change and a re-run, never an edit of the report.

**Three benchmarks, three different questions.**
1. *Agent benchmark* (`bench/run_agent.py`, 20 scenarios in `bench/scenarios.yml`): "does the multi-agent system
   produce a correct, bookable plan, and what does it cost?" Each scenario runs the real graph with the real model,
   approves, and is scored by 12 **deterministic checks** (`bench/checks.py`) — right number of days, dates in order,
   every activity is a real sight from the research, no repeats, flights on the right route and dates, hotel matches
   the stay, the total adds up, the over/under-budget verdict is right, the booking succeeded. No "LLM judge": a
   failed check names a field. We also run it with the scripted fake model as a baseline (20/20) — that proves the
   checks and the graph, so any failure with the real model is the model's.
2. *Load benchmark* (`bench/run_load.py` → k6 in Docker): "how much of the service is ours?" The LLM is stubbed with
   the scripted model, so the number measures FastAPI + LangGraph + Postgres checkpointing + the tool layer at
   2/5/10/20 virtual users. The report says loudly that the LLM is excluded; with a real model, throughput is the
   provider's rate limit, not our code.
3. *Durability* (`bench/durability.py`): "is the human-in-the-loop pause really crash-safe?" Ten times: plan → kill the
   API container → is the thread still awaiting approval? → approve → booked. Pass/fail plus restart time.

**What the first scripted run taught us (before any real model ran).** Groups of 3+ sometimes could not book: the
budgeter picked the cheapest flight without checking `seats_left`. Fix: a capacity gate in code (`nodes.py`), in the
prompt, and in the fake. Also: Dehradun→Rishikesh share an airport (no flight exists) — the scenario was wrong and the
provider now returns no flights for a same-airport pair. The benchmark exists to find exactly this kind of thing.

**Reading the report.** The headline is "scenarios fully passed / 20" plus latency p50/p95 to the proposal and
tokens per trip. The "What this does NOT prove" section is part of the report by design: simulated bookings, offline
tools, structural checks only, one laptop, one run per level, free-tier quotas.
