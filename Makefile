.PHONY: sync up down logs test lint fmt run chat demo

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

demo:            ## (Phase 2) scripted 2-minute demo
	@echo "demo arrives in Phase 2"
