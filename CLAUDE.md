# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run from `agent-observability/`:

```bash
# Install (prefer uv)
make install-uv        # uv venv + all extras (dev, workers, dashboard, sdk)
make install           # pip venv alternative

# Quality
make lint              # ruff check + ruff format --check + mypy
make typecheck         # mypy only (api/ core/ workers/)
make format            # ruff --fix + ruff format

# Tests (requires Docker for postgres + redis, uses isolated project name)
make test              # full suite with coverage (project: agent-observability-test)
make test-quick        # fast, exit on first failure
pytest tests/test_api.py::test_ingest_run -v  # single test

# Services only (for manual testing)
make test-services     # start postgres + redis via docker-compose.dev.yml
make test-services-down

# Run locally
make api               # uvicorn on :8000 (starts services first)
make dashboard         # streamlit on :8501
make worker            # celery worker
make dev               # api + dashboard together

# Docker dev environment
make docker-up         # docker-compose.dev.yml (full stack)
make docker-logs

# Docker production
make docker-prod-up    # docker-compose.yml (production stack)

# CI (what the pipeline runs)
make ci                # lint + test
```

## Architecture

The project is a **multi-tenant LangGraph observability platform** with four layers:

### `api/` — FastAPI REST API
- `main.py` defines 11 endpoints under `/api/v1/` plus `/health`
- Auth injected via FastAPI `Depends`: `get_tenant_from_api_key` (X-API-Key header for ingestion) and `get_authenticated_tenant` (X-API-Key or Bearer JWT for read endpoints — falls back gracefully)
- Schema auto-creation on startup; demo tenant seeded via `INSERT ... ON CONFLICT (name) DO NOTHING` (safe for multi-worker startup)
- CORS middleware configured with `allow_origins=["*"]`
- All DB calls use async SQLAlchemy sessions via `get_db` dependency

### `core/` — Shared layer
- `models.py`: 7 SQLAlchemy ORM models — `Tenant → Agent → AgentRun → AgentSpan/Anomaly`, plus `Alert` and `AuditLog`. UUID PKs, JSONB for metadata/evidence
- `schemas.py`: Pydantic v2 request/response models
- `config.py`: `Settings` via pydantic-settings, all env vars prefixed `AGENT_OBS_`, `extra="ignore"` for flexibility
- `database.py`: async engine + `async_session` factory + `get_db` generator

### `workers/` — Celery async tasks
- `tasks.py`: `analyze_run` (triggered post-ingest), `purge_old_traces` (daily cron)
- `detectors.py`: `detect_loops` (5 identical consecutive outputs = infinite_loop anomaly) and `detect_hallucinations` (LLM-as-judge via OpenAI/OpenRouter, confidence > 0.7 threshold)
- `celery_app.py`: broker on Redis DB 1, result backend on Redis DB 2

### `sdk/` — Separate pip package (`agent-obs-sdk`)
- Installed via `pip install -e sdk/` (its own `pyproject.toml`)
- Exposes `AgentObservabilityClient`, `@monitor` decorator, `ObservabilityCallback` (LangChain/LangGraph)
- mypy is configured to skip the `sdk/` directory

### `dashboard/` — Streamlit app
- `app.py`: 5-tab UI (Metrics, Traces, Anomalies, Alerts, Costs) polling the REST API
- Default API key: `demo-key-local-dev`

## Key conventions

- **Line length**: 130 chars (ruff + mypy configured accordingly)
- **mypy scope**: `api/`, `core/`, `workers/` only — not `sdk/` or `tests/`
- **Test env vars**: `AGENT_OBS_DATABASE_URL`, `AGENT_OBS_REDIS_URL`, `AGENT_OBS_SECRET_KEY` must be set; `conftest.py` creates/drops schema per session using a real PostgreSQL instance (no mocking)
- **Test isolation**: `make test` uses `-p agent-observability-test` to avoid conflicting with production containers
- **Demo key**: `demo-key-local-dev` (both dashboard default and auto-seed tenant API key)
- **Tenant isolation**: every query filters by `tenant_id` — never omit this where clause
- **Ingest endpoint** (`POST /api/v1/ingest`) uses API Key auth only (not JWT); read endpoints accept both
- **Startup safety**: demo tenant seed uses `ON CONFLICT (name) DO NOTHING` — safe for concurrent uvicorn workers
