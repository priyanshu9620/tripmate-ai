.PHONY: sync up down logs test lint fmt run chat demo migrate bench durability load report infra-init infra-plan infra-apply infra-destroy infra-output

sync:            ## install deps (uv)
	uv sync

up:              ## build + start api + postgres  → http://localhost:8000/ui
	docker compose up -d --build

down:            ## stop everything (keeps the postgres volume)
	docker compose down

logs:
	docker compose logs -f api

test:            ## offline tests, fake LLM, no network
	LLM_PROVIDER=fake uv run pytest -q -p no:warnings

lint:
	uv run ruff check src tests && uv run ruff format --check src tests

fmt:
	uv run ruff format src tests && uv run ruff check --fix src tests

run:             ## run the API from the venv (uses .env; postgres from `make up`)
	uv run tm serve

chat:            ## terminal chat against a running server
	uv run tm chat

demo:            ## scripted 2-minute demo against the running stack (DEMO.md)
	uv run python scripts/demo.py

migrate:         ## apply DB migrations to DATABASE_URL (the API also does this at startup)
	uv run alembic upgrade head

# ---- measurement (bench/README in docs/GUIDE.md) ----
bench:           ## agent benchmark with the real model from .env (20 scenarios; ~120 LLM requests)
	uv run python bench/run_agent.py

bench-fake:      ## same benchmark with the scripted model (seconds, no key)
	uv run python bench/run_agent.py --provider fake

durability:      ## 10× kill the API mid-approval and resume (needs make up with Postgres)
	uv run python bench/durability.py 10

load:            ## k6 in Docker at 2/5/10/20 VUs against the API running with LLM_PROVIDER=fake
	uv run python bench/run_load.py

report:          ## regenerate bench/report.md + charts + bench/results.json from the latest runs
	uv run python bench/report.py

# ---- AWS (infra/, OpenTofu). Claude prepares + plans; the user runs apply/destroy (billable). ----
TOFU = tofu -chdir=infra

infra-init:
	$(TOFU) init -input=false

infra-plan:      ## read-only: shows what apply would create
	$(TOFU) plan -input=false -out=plan.out

infra-apply:     ## creates billable resources (t3.micro + ALB ≈ $1/day); review infra-plan first
	$(TOFU) apply -input=false plan.out

infra-destroy:   ## tears everything down (ECR images included) — run after every session
	$(TOFU) destroy -input=false

infra-output:
	$(TOFU) output

# ---- portability: secrets travel in ONE encrypted archive (secrets.tar.enc), notes travel as plain files ----
secrets-pack:    ## SECRETS_PASSPHRASE=... make secrets-pack   (then commit secrets.tar.enc)
	scripts/secrets.sh pack

secrets-unpack:  ## SECRETS_PASSPHRASE=... make secrets-unpack (fresh clone: restores .env, tfvars, tfstate)
	scripts/secrets.sh unpack
