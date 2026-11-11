# Resume lines — rewritten with measured numbers (2026-11-11)

**TripMate AI: Multi-Agent Trip Planner** | LangGraph, FastAPI, PostgreSQL, Docker, AWS · 2026 · github.com/priyanshu9620/tripmate-ai

- Designed and delivered a multi-agent trip planner: 4 specialised LangGraph agents with 7 tools, a human-in-the-loop
  approval interrupt before any booking, and conversation + preference memory in PostgreSQL; a 20-scenario benchmark with
  12 deterministic checks each passes 20/20 (Gemini flash-lite, p50 25 s to a proposal, ~6 LLM + 6 tool calls per trip),
  and the pending approval survived 10/10 forced API restarts.
- Shipped it to AWS (EC2 + ALB + ECR, OpenTofu) through a GitHub Actions CI/CD pipeline that builds the Docker image and
  deploys via SSM with ALB health gating; served by FastAPI with SSE streaming, measured at 33 trips/s (p95 442 ms, 0
  errors) with the model stubbed; traced and debugged agent runs with LangSmith.

Every number: `bench/report.md`, `bench/results.json`, `docs/aws-evidence.md`. Re-run `make bench`/`make load`/
`make durability` + `make report` before quoting again.
