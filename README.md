# TripMate AI — multi-agent trip planner

> Phase 0 skeleton. A supervisor + four specialised LangGraph agents (researcher, planner, budgeter, booker) with
> tool calling, a human-in-the-loop approval pause before any booking, and conversation memory in PostgreSQL —
> served by FastAPI, containerised with Docker, deployed to AWS by GitHub Actions. Bookings are simulated.

## Run it

```
cp .env.example .env     # optional: add a model key; without one the fake echo model is used
make up                  # api + postgres → http://localhost:8000/ui
make chat                # terminal chat
make test                # offline tests, no network
```

## Tools (Phase 1)
Seven LangChain tools in `src/tripmate/tools/`: `geocode`, `weather_forecast`, `points_of_interest` (live via
Nominatim / Open-Meteo / Overpass when `TOOLS_MODE=live`, curated fixtures otherwise, with automatic fallback),
`search_flights`, `search_hotels` (simulated, deterministic inventory in `providers/`), and the two mutating tools
`book_flight`, `book_hotel` (idempotent, in-process ledger). `uv run tm tools demo --destination Goa` shows them.

## Measured numbers
Arrive in Phase 3 (`bench/`). Nothing here is asserted by hand.

## Roadmap
0 skeleton ✔ · 1 tools ✔ · 2 multi-agent graph + HITL + Postgres memory · 3 measurement · 4 AWS + CD · 5 interview material
