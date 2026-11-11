# Phase 0 — what exists and why (plain English)

- **`src/tripmate/config.py`** reads `.env` into a Settings object *and* into the process environment. Two readers because
  our code uses Settings, but provider SDKs (Google, Anthropic) only look at environment variables (Pager-Zero P-7).
- **`llm.py`** has one function, `get_model()`. `LLM_PROVIDER=fake` returns a tiny echo model; anything else goes to
  LangChain's `init_chat_model`, so swapping provider is a `.env` edit. The fake model is what tests, CI and the load
  bench use — no key, no network, deterministic.
- **`graph.py`** is the smallest possible LangGraph: START → assistant → END, compiled with a checkpointer. The
  checkpointer is what makes a `thread_id` remember earlier turns (see the test: 2 turns → 4 messages). Phase 2 swaps
  the in-memory checkpointer for Postgres and the single node for the supervisor + 4 agents.
- **`api.py`** exposes threads and messages, `/healthz` (version, provider, Postgres ping), `/metrics` (Prometheus text —
  the bench scrapes this), and `/ui` (one static HTML file, no build step).
- **`docker-compose.yml`** runs the API image + Postgres. Postgres is on host port **5433** because 5432 is usually taken on
  a developer laptop. The API container talks to Postgres on the internal network at 5432.
- **CI** runs lint + tests with the fake model, then builds the image and curls `/healthz` inside the runner — so a broken
  Dockerfile fails the PR, not the deploy.
