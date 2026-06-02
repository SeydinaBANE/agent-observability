# Agent Observability Dashboard

[![CI](https://github.com/your-org/agent-observability/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/agent-observability/actions/workflows/ci.yml)

**Plateforme de monitoring production-grade pour agents LangGraph.** Ingestion temps réel, détection d'anomalies (hallucinations, boucles infinies), dashboard multi-tenant, et alerting.

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
# 1. Cloner et installer
git clone <url>
cd agent-observability
pip install -e ".[dev,dashboard,workers]"
pip install -e sdk/

# 2. Démarrer les services (PostgreSQL + Redis)
make services

# 3. Lancer l'API
make dev-api

# 4. (Nouveau terminal) Dashboard
make dev-dashboard
```

- **API** : http://localhost:8000
- **Docs Swagger** : http://localhost:8000/docs
- **Dashboard** : http://localhost:8501 (clé API : `demo-key-1234567890123456`)

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

@monitor(agent_id="mon-agent", api_key="ta-clé")
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
