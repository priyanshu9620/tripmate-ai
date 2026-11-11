# The plan in plain English

**What we are building.** A trip planner where you chat ("Goa, 4 days, ₹40k, 2 people, we like beaches") and a team of
AI agents does the work: one researches the place (weather, sights), one writes the day-by-day plan, one prices flights
and hotels against your budget, and one books — but only after you say yes. The conversation is saved in Postgres, so you
can close the app, come back tomorrow, and continue; and your preferences carry across trips.

**Why several agents instead of one prompt.** Each agent has a small job and a small set of tools, so it is easier to
test, cheaper (fewer tokens per call), and the routing between them is plain code you can unit-test without an LLM.

**Why the "approval pause" matters.** Booking is the one irreversible action. LangGraph can pause the graph, save its
state, and resume later from the saved state — even after a restart. That is the human-in-the-loop claim, and we prove
it by killing the server mid-pause.

**What is real and what is simulated.** Weather, geocoding and sights come from free public APIs. Flights and hotels are
simulated with fixed inventory because there is no free real API; the README says so.

**How we get numbers.** A script runs 20 fixed trips and records latency, tokens, cost, and whether the plan obeys the
constraints. A second script hammers the API with the LLM stubbed to measure the server itself. A third kills and
resumes the server 10 times. The report is generated from those runs; nothing is typed in by hand.

**AWS.** One small server behind a load balancer, created by Terraform, deployed by GitHub Actions on every merge,
destroyed right after we have the screenshots. It costs money only while it is up.
