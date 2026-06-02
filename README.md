# Agent Observability Dashboard

<p align="center">
  <img src="https://img.shields.io/github/actions/workflow/status/SeydinaBANE/agent-observability/ci.yml?branch=main&label=CI&logo=github" alt="CI">
  <img src="https://img.shields.io/github/license/SeydinaBANE/agent-observability" alt="License">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Celery-5.4-37814A?logo=celery" alt="Celery">
  <img src="https://img.shields.io/badge/Streamlit-1.41-FF4B4B?logo=streamlit" alt="Streamlit">
  <img src="https://img.shields.io/badge/Docker-compose-2496ED?logo=docker" alt="Docker">
  <img src="https://img.shields.io/badge/coverage-62%25-yellowgreen" alt="Coverage">
  <img src="https://img.shields.io/badge/uses-LangGraph-1E3A5F" alt="LangGraph">
  <br>
  <strong>Plateforme de monitoring production-grade pour agents LangGraph.</strong><br>
  Ingestion temps réel · Détection d'anomalies (hallucinations, boucles infinies) · Dashboard multi-tenant · Alerting
</p>

---

## Fonctionnalités

| Fonctionnalité | Statut |
|----------------|--------|
| Ingestion traces agents (runs, spans, tokens, coûts) | ✅ |
| Dashboard temps réel (Streamlit + Plotly) | ✅ |
| Détection d'anomalies (hallucinations + boucles infinies) | ✅ |
| Multi-tenant (isolation par API Key / JWT) | ✅ |
| SDK Python (décorateur `@monitor` + callback LangGraph) | ✅ |
| Alerting multi-canal | ✅ |
| Suivi des coûts par agent | ✅ |
| Rétention + purge automatique des données | ✅ |
| Grafana dashboards (3 pré-configurés) | ✅ |
| CI/CD complet (GitHub Actions + Docker + Trivy) | ✅ |

---

## Quickstart

```bash
# 1. Cloner
git clone https://github.com/SeydinaBANE/agent-observability
cd agent-observability

# 2. Tout en une commande (Docker)
docker compose up -d --build

# 3. Ou en local (dev)
pip install -e ".[dev,dashboard,workers]" && pip install -e sdk/
./dev-cli.py start
```

- **API** : http://localhost:8000
- **Docs Swagger** : http://localhost:8000/docs
- **Dashboard** : http://localhost:8501 (clé API : `demo-key-local-dev`)
- **Health** : `curl http://localhost:8000/health`

---

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/ARCHITECTURE.md) | Vue d'ensemble technique |
| [API REST](docs/API.md) | Documentation des endpoints |
| [SDK Python](docs/SDK.md) | Guide du SDK `agent-obs-sdk` |
| [Guide développement](docs/GUIDE_DEVELOPPEMENT.md) | Setup, tests, conventions |
| [Déploiement](docs/DEPLOIEMENT.md) | Docker, production, monitoring |

---

## Usage SDK

Décorateur simple :

```python
from agent_obs import monitor

@monitor(agent_id="mon-agent", api_key="demo-key-local-dev")
async def mon_agent(query: str) -> str:
    return await process(query)
```

Callback LangGraph pour tracing complet (chaînes, LLM, outils) :

```python
from agent_obs import AgentObservabilityClient, ObservabilityCallback

client = AgentObservabilityClient(api_key="ta-clé", agent_id="mon-agent")
callback = ObservabilityCallback(client)

# Intégration dans LangGraph
graph.invoke({"input": "question"}, {"callbacks": [callback]})
callback.flush(input_preview="question", output_preview=str(result))
```

---

## Stack

| Couche | Technologie |
|--------|-------------|
| API | FastAPI + Uvicorn |
| Base de données | PostgreSQL 16 (asyncpg) |
| Cache / Queue | Redis 7 |
| Workers | Celery 5.4 |
| Dashboard | Streamlit + Plotly |
| SDK | httpx + LangGraph |
| Monitoring | Grafana |
| CI/CD | GitHub Actions |

---

## Licence

MIT
