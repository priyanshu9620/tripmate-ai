---
name: tripmate-project
description: TripMate AI resume project #3 (LangGraph multi-agent trip planner) — notes ~/Desktop/tripmate-notes, repo ~/Desktop/tripmate = github priyanshu9620/tripmate-ai (private until Phase 2)
metadata:
  type: project
---

Third "make my resume project real" project, started 2026-11-11. Resume lines were borrowed from someone else's resume as a writeup only; nothing exists, everything is built from scratch for the user's own GitHub (`priyanshu9620`, identity Priyanshu Gupta <guptapriyanshu1822@gmail.com>).

Notes: `~/Desktop/tripmate-notes` (read `session/HANDOFF.md` first). Repo: `~/Desktop/tripmate` → `priyanshu9620/tripmate-ai` (private; public repo creation is denied by the permission classifier, user flips visibility at Phase 2).
Status 2026-11-11: Phases 0-2 on main, repo public, LangSmith live (key in repo .env; rotate at end). NO PRs: commit directly to main (D-19). Phase 3 done 2026-11-11 (Gemini 20/20 p50 25s; load 33 trips/s; durability 10/10). Phase 4 infra code on main, plan = 22 resources, WAITING for user `make infra-apply`; then Claude sets gh secrets + runs deploy; then Phase 5. Gemini key copied into the repo `.env`; LangSmith account to be created at Phase 2.

**Why:** the user wants a new session to resume from HANDOFF.md alone.
**How to apply:** follow the same method as [[pager-zero-project]] and [[shopease-project]]; default LLM gemini-3.5-flash-lite (free), AWS via profile `shopease` in ap-southeast-2 (ShopEase D-21). Claude never runs terraform apply/destroy.
