.PHONY: install install-dev lint typecheck test format format-check clean build docker-build docker-up docker-down docker-logs ci run api dashboard worker

VENV = .venv
PYTHON = python3
PIP = $(VENV)/bin/pip
UV = uv

# ─── Installation ──────────────────────────────────────────────────────────────

install:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -e ".[dev,workers,dashboard,sdk]"
	$(PIP) install -e sdk/

install-uv:
	uv venv
	uv pip install -e ".[dev,workers,dashboard,sdk]"
	uv pip install -e sdk/

install-precommit:
	$(PIP) install pre-commit
	$(VENV)/bin/pre-commit install

# ─── Qualité ───────────────────────────────────────────────────────────────────

lint:
	ruff check .
	ruff format --check .
	mypy api/ core/ workers/

typecheck:
	mypy api/ core/ workers/

format:
	ruff check --fix .
	ruff format .

# ─── Tests ─────────────────────────────────────────────────────────────────────

install-sdk:
	pip install -q -e sdk/ 2>/dev/null || true

test-services:
	docker compose -p agent-observability-test -f docker-compose.dev.yml up -d postgres redis --wait

test-services-down:
	docker compose -p agent-observability-test -f docker-compose.dev.yml down

test: install-sdk test-services
	AGENT_OBS_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/agent_obs \
	AGENT_OBS_REDIS_URL=redis://localhost:6379/0 \
	AGENT_OBS_SECRET_KEY=test-key \
	pytest tests/ -v --cov=api --cov=core --cov=workers --cov-report=term-missing
	$(MAKE) test-services-down

test-quick: install-sdk test-services
	AGENT_OBS_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/agent_obs \
	AGENT_OBS_REDIS_URL=redis://localhost:6379/0 \
	AGENT_OBS_SECRET_KEY=test-key \
	pytest tests/ -v -x --no-header
	$(MAKE) test-services-down

test-watch:
	 AGENT_OBS_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/agent_obs \
	 AGENT_OBS_REDIS_URL=redis://localhost:6379/0 \
	 AGENT_OBS_SECRET_KEY=test-key \
	 ptw tests/ -- --testmon

# ─── CI ────────────────────────────────────────────────────────────────────────

ci: lint test
	@echo "✓ CI passed"

# ─── Build ─────────────────────────────────────────────────────────────────────

build:
	$(PIP) wheel --no-deps -w dist/ .
	$(PIP) wheel --no-deps -w dist/ sdk/

docker-build:
	docker compose build

docker-push:
	docker compose push

# ─── Docker ────────────────────────────────────────────────────────────────────

docker-up:
	docker compose -f docker-compose.dev.yml up -d --build

docker-down:
	docker compose -f docker-compose.dev.yml down

docker-logs:
	docker compose -f docker-compose.dev.yml logs -f

docker-prod-up:
	docker compose up -d --build

docker-prod-down:
	docker compose down

docker-clean:
	docker system prune -f

# ─── Run (local, sans Docker) ──────────────────────────────────────────────────

api: test-services
	uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

dev: test-services
	uvicorn api.main:app --reload --host 0.0.0.0 --port 8000 &
	sleep 3
	streamlit run dashboard/app.py --server.port=8501

dashboard:
	streamlit run dashboard/app.py --server.port=8501

worker:
	celery -A workers.tasks worker --loglevel=info --concurrency=4

beat:
	celery -A workers.tasks beat --loglevel=info

# ─── Utilitaires ───────────────────────────────────────────────────────────────

clean:
	rm -rf $(VENV) __pycache__ .pytest_cache .ruff_cache .mypy_cache *.egg-info dist/ build/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete

refresh: clean install
	@echo "✓ Fresh install done"

# ─── Help ──────────────────────────────────────────────────────────────────────

help:
	@echo "Usage:"
	@echo "  make install          Create venv + install all deps"
	@echo "  make install-uv       Install via uv"
	@echo "  make lint             Run ruff + mypy"
	@echo "  make typecheck        Run mypy only"
	@echo "  make format           Auto-format code"
	@echo "  make test             Run tests with coverage"
	@echo "  make test-quick       Run tests fast (exit first error)"
	@echo "  make ci               Lint + test (CI pipeline)"
	@echo "  make docker-up        Start dev environment"
	@echo "  make docker-down      Stop dev environment"
	@echo "  make docker-prod-up   Start production"
	@echo "  make api              Run API locally"
	@echo "  make dashboard        Run Streamlit locally"
	@echo "  make clean            Remove all artifacts"
	@echo "  make refresh          Clean + reinstall"
	@echo ""
	@echo "📘 Documentation :"
	@echo "  DEMO.md       Guide de démonstration pas à pas"
	@echo "  DEV.md        Guide de développement"
	@echo "  BUILD.md      Build & packaging"
	@echo "  PROD.md       Déploiement production"
	@echo "  TESTING.md    Guide des tests"
	@echo "  docs/         Documentation complémentaire (API, SDK, ARCHITECTURE)"
