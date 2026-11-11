# TripMate AI — 2-minute demo

```
make up                       # api + postgres (reads .env: set LLM_PROVIDER / key, or leave fake)
make demo                     # runs scripts/demo.py
```

What to say while it runs:

1. **"One message, four agents."** Intake extracts the constraints; the researcher calls geocode, weather and sights
   tools; the planner writes the day-by-day itinerary; the budgeter searches flights and hotels and fits them into
   the budget. The SSE stream prints each agent as it finishes.
2. **"It stops before spending money."** The graph hits a LangGraph `interrupt()` in front of the booker. Nothing is
   booked. The proposal shows the total against the budget.
3. **"The pause survives a crash."** We restart the API container. The thread state, including the pending
   interrupt, is in Postgres through the LangGraph checkpointer, so the thread resumes where it was.
4. **"Approval books exactly what was approved."** The booker is deterministic code, not an LLM: it books the three
   items in the proposal and records the trip in the `trips` table.
5. **"Memory across trips."** A new thread for the same user starts with the saved preferences (LangGraph store).

Open `http://127.0.0.1:8000/ui?thread=<id>` during the demo to show the same conversation in the browser, with the
Approve / Reject buttons.
