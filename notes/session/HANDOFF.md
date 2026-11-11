# HANDOFF — read this first

**Project:** TripMate AI — multi-agent trip planner (LangGraph, FastAPI, PostgreSQL, Docker, AWS). Resume project for Priyanshu Gupta.
The two resume lines were taken from someone else's resume as a *writeup only*; nothing exists yet. Everything is built from scratch.
**Code:** `~/Desktop/tripmate` · GitHub `priyanshu9620/tripmate-ai` (private until Phase 2, D-16/P-1) · **Notes:** `~/Desktop/tripmate-notes` (this folder).

## Resume lines this must satisfy (verbatim, as given 2026-11-11)
TripMate AI: Multi-Agent Trip Planner | LangGraph, FastAPI, PostgreSQL, Docker, AWS · 2026
- Designed and delivered a multi-agent trip planner, by orchestrating specialized agents in LangGraph with tool calling,
  human-in-the-loop approval and persistent conversation memory in PostgreSQL.
- Shipped the agents to AWS through a GitHub Actions CI/CD pipeline, by serving them via FastAPI and containerizing with
  Docker; traced and debugged agent runs with LangSmith.

Neither line has a number. Measured numbers get added (D-9) and the lines are rewritten at the end.

## Where we are
**2026-11-11 night:** Phases 0–4 code on `main`. Phase 4 infra is planned (22 resources, `infra/plan.out`) and
**waits for the user to apply** (Claude Code policy blocks `tofu apply`, ShopEase P-21). Bootstrap order after apply:
(1) Claude: `gh secret set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY` from `tofu output`, `gh variable set AWS_DEPLOY_ENABLED=true`,
`gh workflow run deploy`; (2) verify `/healthz` + a real conversation through the ALB; (3) screenshots → `docs/`; (4) user runs
`make infra-destroy`. `infra/terraform.tfvars` (git-ignored) already holds the Gemini + LangSmith keys.

Earlier: Phases 0–3 are on `main`. Measured numbers are in PROGRESS (Gemini 20/20, p50 25 s; load 33 trips/s;
durability 10/10) and in `bench/report.md`. Next: **Phase 4 AWS + CD** (billable; Claude prepares Terraform + deploy.yml,
user runs apply/destroy), then Phase 5 interview material + resume rewrite.

Earlier: Phases 0, 1 and 2 are on `main`. The multi-agent graph, approval interrupt, Postgres memory, API/CLI/UI
and `make demo` all work with Gemini (numbers in PROGRESS). Repo is public; LangSmith tracing is live (project `tripmate-ai`, key in repo `.env`, rotate after the project).
Nothing owed by the user. Next: **Phase 3 measurement** — `bench/` with 20 scenarios,
k6 load with `LLM_PROVIDER=fake`, durability loop, generated `report.md` + charts.

Earlier: Phase 0 is on `main` (PR #1 merged by fast-forward, then the user asked for no more PRs — D-19).
Local stack is up (`make up`): api + postgres, `/ui` chat works with the fake model; one real Gemini call through the graph
verified (1.8 s, 11 tokens). `.env` in the repo holds the Gemini key (git-ignored).  LangSmith account still to be created at Phase 2 (kt/01).

## How to work
1. Read `DECISIONS.md`; append, never rewrite. If something must change, append a superseding decision.
2. Follow `BUILD-PLAN.md` phase order; each phase ends runnable and documented. Commit directly to `main`, one commit per milestone (D-19, no PRs).
3. Log problems in `PROBLEMS.md`, progress in `PROGRESS.md`; keep `kt/` current after every milestone, not at the end.
4. Commit as `Priyanshu Gupta <guptapriyanshu1822@gmail.com>` (set per clone — the global identity is the work email).
   `gh auth switch -u priyanshu9620` before any `gh repo` / `gh pr` call; push via the token-header one-off
   (pager-zero-notes P-5) unless SSH is set up.
5. Anything billable (AWS stack) is created by Terraform and destroyed by `terraform destroy`; Claude prepares and shows the
   plan, the user runs apply/destroy. Never leave the stack up overnight without the user's OK.
6. Reuse what the earlier projects learned: free working model is `google_genai` / `gemini-3.5-flash-lite` (Pager-Zero);
   Anthropic key has no credits; Groq free tier too small. AWS = profile `shopease`, region `ap-southeast-2`, free-plan
   project with SCP (EC2/ELB/ECS/S3/CloudFront allowed, App Runner denied) — see shopease-notes D-21.

## Single next command
User: `cd ~/Desktop/tripmate && git push && make infra-apply` (2 changes) then tell Claude; Claude re-deploys + verifies; then user `make infra-destroy` and `SECRETS_PASSPHRASE=… make secrets-pack && git commit -am 'chore: secrets' && git push`.
