# 06 · Likely questions — answers in my voice

**Why multiple agents instead of one big prompt?**
Each agent has a small job and a small tool set, so prompts stay short, failures are local, and I can test each node
alone. The supervisor is plain code over typed state — routing cannot hallucinate. One prompt would have to hold
research, planning and pricing at once and I could not verify any of it.

**How does the human-in-the-loop work technically?**
The approval node calls LangGraph's `interrupt()` with the proposal. LangGraph checkpoints the state and returns to the
API with status `awaiting_approval`. The client resumes with `Command(resume={"decision": "approve"})` and execution
continues from that line into the booker. Because the interrupt is a checkpoint in Postgres, a new process can resume
it — I kill the API container mid-approval 10 times in the durability test and it resumes 10/10.

**What is stored in PostgreSQL exactly?**
Three things: the LangGraph checkpoints per thread (every node's output — that is the conversation memory), the
LangGraph store for per-user preferences across threads, and a `trips` table with the final itinerary and booking
references so listing trips never replays a graph.

**How do you keep the LLM from doing something wrong with money?**
Three layers. The booker is deterministic code, not a model. Before that, the budgeter's picks are re-validated against
the real search results, filtered for seat/room capacity, and replaced by a fitting combination if over budget. And a
human approves the exact proposal.

**How did you measure it?**
Twenty fixed scenarios through the real graph, scored by twelve deterministic checks each — day count, dates, real
sights, no repeats, flights on the right route and dates, hotel matches the stay, totals add up, budget verdict,
booking succeeded. Gemini flash-lite passes 20/20, p50 25 s to a proposal, about 6 LLM and 6 tool calls, ~6k tokens.
Separately I load-test the service with the model stubbed — 33 trips/s at 20 virtual users, p95 442 ms — and I say
clearly that the LLM is excluded there.

**What does the benchmark NOT prove?**
Bookings are simulated, the checks are structural not qualitative, tools ran offline, one laptop, one run per level,
free-tier quotas. It is in the report on purpose.

**What broke in production?**
The ALB's 60-second idle timeout cut a 61-second turn while the server finished the work. I raised the timeout to 300 s
and the SSE endpoint exists for exactly this. Also the model proposed over budget once for a scenario that passed in
the bench; now code repairs that.

**Why Gemini flash-lite?**
Free tier that actually works for tool calling; the provider is a `.env` setting, so swapping is zero code. I report the
model with every number.

**How is it deployed?**
OpenTofu builds one EC2 instance running the compose stack behind an ALB, an ECR repo, SSM parameters for secrets, a
scoped IAM user. GitHub Actions builds the amd64 image, pushes to ECR, runs the deploy script through SSM Run Command,
waits for the ALB health check, then smoke-tests `/healthz`. Three green runs; destroyed after the session.

**What would you do next?**
Real inventory via a sandbox API behind the same provider interface; more uvicorn workers (the load plateau is one
worker); an LLM-judge for itinerary quality alongside the structural checks; a second model in the benchmark table.

**Biggest lesson?**
A cheap, deterministic baseline (the scripted model + checks) found two product bugs before I spent a single real
model request. And: every "graceful fallback" needs a loud signal, or it becomes a silent downgrade.
