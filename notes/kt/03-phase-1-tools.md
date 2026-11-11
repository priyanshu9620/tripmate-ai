# Phase 1 — tools and providers (plain English)

**A "tool" is a Python function the LLM is allowed to call.** LangChain's `@tool` turns the function's signature and
docstring into a schema the model sees; when the model answers with a tool call, LangGraph runs the function and feeds
the result back. Our seven tools live in `src/tripmate/tools/__init__.py`.

**Two kinds of tools.** Research tools (`geocode`, `weather_forecast`, `points_of_interest`) read the world. Search
tools (`search_flights`, `search_hotels`) read our simulated inventory. Booking tools (`book_flight`, `book_hotel`)
*change* state — that set is `MUTATING_TOOL_NAMES`, and Phase 2 puts the human-approval pause in front of exactly those.

**Offline-first.** `TOOLS_MODE=offline` (default) answers from fixtures so tests, CI and the benchmark need no network
and always give the same answer. `TOOLS_MODE=live` calls Nominatim (geocoding), Open-Meteo (weather, 16-day window;
beyond that we use monthly climate normals and *say so* in `source`) and Overpass (sights). Every live call has an 8 s
timeout and falls back to the fixture — the demo showed Overpass timing out and the tool still answering (P-2).

**Why simulate flights and hotels.** There is no free real inventory API. The providers are pure functions: the same
route + date always returns the same five flights and prices (seeded random from a hash of the inputs), so a benchmark
run today and next month compares like with like. Rates have a season multiplier (Goa in December costs more than in
July — there is a test for that) so the budget agent has real trade-offs to reason about.

**Booking safety even before the LLM.** `book_flight` refuses an id that did not come from a search in this process,
refuses empty traveller lists and oversold seats, and the same (flight, travellers) always yields the same reference
(`already_booked: true` on repeat) — idempotency, so a retried tool call cannot double-book.

**Interview line.** "Tools return dicts, never bare lists" — some providers reject an empty list as tool content; we
learned that in the first project and designed around it here from day one.
