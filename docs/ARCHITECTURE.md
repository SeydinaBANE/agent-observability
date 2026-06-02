# Architecture — Agent Observability Dashboard

## Vue d'ensemble

Agent Observability Dashboard est une plateforme de monitoring **multi-tenant** conçue pour surveiller, tracer et détecter les anomalies d'agents LangGraph en production. Elle suit une architecture en couches avec ingestion asynchrone, détection d'anomalies par workers Celery, et visualisation via Streamlit.

```
┌─────────────────────────────────────────────────────┐
│                   Dashboard (Streamlit)              │
│   Métriques │ Traces │ Anomalies │ Alertes │ Coûts   │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────────┐
│                 API REST (FastAPI)                    │
│   /tenants /agents /ingest /metrics /traces          │
│   /anomalies /alerts /dashboard /costs /auth/token   │
│   11 endpoints au total sous /api/v1/                │
│   Auth: X-API-Key ou Bearer JWT (multi-tenant)       │
│   CORS: allow_origins=["*"]                          │
└──────┬──────────────────────┬───────────────────────┘
       │                      │
┌──────▼──────┐      ┌───────▼──────────────────────┐
│ PostgreSQL  │      │     Redis (Celery + Cache)    │
│  + Timescale│      │  broker / result backend      │
└─────────────┘      └───────┬──────────────────────┘
                             │
                      ┌──────▼──────────────────────┐
                      │     Workers (Celery)         │
                      │  • Détection de boucles      │
                      │  • Détection d'hallucinations│
                      │  • Purge des anciennes traces │
                      └─────────────────────────────┘
```

## Composants

### 1. API REST (`api/`)
Framework **FastAPI** avec 11 endpoints organisés sous `/api/v1/`.

- Authentification multi-tenant via **X-API-Key** (hash bcrypt) ou **Bearer JWT** (fallback automatique)
- Dépendances d'injection via `get_db`, `get_tenant_from_api_key`, `get_authenticated_tenant`, `_get_tenant_from_api_key_optional`
- Validation des entrées via Pydantic v2 (`core/schemas.py`)
- Documentation interactive : `/docs` (Swagger) et `/redoc`
- **CORS** : middleware configuré avec `allow_origins=["*"]`
- **Startup** : création automatique des tables + seed du tenant `demo` via `INSERT ... ON CONFLICT (name) DO NOTHING` (sûr pour démarrage multi-worker)

### 2. SDK Client (`sdk/`)
Package Python `agent-obs-sdk` qui expose :

- **`AgentObservabilityClient`** : client HTTP avec retry exponentiel, batching, session tracking
- **`@monitor`** : décorateur pour instrumenter n'importe quelle fonction
- **`ObservabilityCallback`** : callback LangChain/LangGraph pour capturer automatiquement chaînes, appels LLM et outils

### 3. Workers (`workers/`)
Tâches asynchrones Celery avec Redis comme broker :

| Tâche | Déclencheur | Description |
|-------|-------------|-------------|
| `analyze_run` | Post-ingestion | Détection de boucles infinies + hallucinations |
| `purge_old_traces` | Cron (quotidien) | Nettoie les spans/runs de plus de 7 jours |

**Détection de boucles** : analyse les 20 dernières exécutions d'une session ; si 5 sorties consécutives sont identiques, signale une anomalie critique.

**Détection d'hallucinations** : utilise GPT-4o-mini (ou Ollama) comme LLM-as-judge pour comparer input/output.

### 4. Dashboard (`dashboard/`)
Application **Streamlit** avec 5 onglets :

- **Metrics** : graphiques de performance (temps de réponse, tokens, coûts)
- **Traces** : historique des runs avec filtrage
- **Anomalies** : hallucinations et boucles détectées
- **Alerts** : alertes de dépassement de seuil
- **Costs** : répartition des coûts par agent

Clé API par défaut : `demo-key-local-dev` (configurable via `AGENT_OBS_DASHBOARD_API_KEY`).

### 5. Grafana (`grafana/`)
3 dashboards pré-configurés au format JSON :

- `agent-obs-overview.json` : vue d'ensemble des métriques
- `agent-obs-anomalies.json` : suivi des anomalies
- `agent-obs-costs.json` : analyse des coûts

## Flux de données

```
Agent LangGraph
     │
     ├── [SDK] @monitor decorator
     │         ou ObservabilityCallback
     │
     ▼
POST /api/v1/ingest  (avec X-API-Key)
     │
     ├── Validation Pydantic
     ├── Insertion AgentRun + AgentSpan
     ├── Publication tâche Celery (analyze_run)
     │
     ▼
Worker Celery
     │
     ├── detect_loops() → Anomaly (infinite_loop)
     └── detect_hallucinations() → Anomaly (hallucination)
```

## Authentification

Deux méthodes supportées, vérifiées via `get_authenticated_tenant` :

1. **API Key** : header `X-API-Key` → hash bcrypt stocké dans `tenants.api_key_hash`
2. **Bearer JWT** : header `Authorization: Bearer <token>` → JWT signé avec HS256

Le mécanisme de fallback fonctionne ainsi :
1. `_get_tenant_from_api_key_optional` tente l'API Key (retourne `None` si absent, pas d'erreur)
2. `get_tenant_from_bearer` tente le JWT Bearer (retourne `None` si absent)
3. `get_authenticated_tenant` utilise la première méthode qui trouve un tenant, ou lève `401`

Les clés API sont hachées avec bcrypt via `passlib` (`bcrypt>=4.0,<5.0` pour compatibilité). Le JWT contient `sub` (tenant_id), `agent_id` (optionnel), `exp`, `iat`.

## Modèle de données

7 tables PostgreSQL avec JSONB pour les données semi-structurées :

| Table | Rôle | Clé étrangère |
|-------|------|---------------|
| `tenants` | Locataires multi-tenant | — |
| `agents` | Agents enregistrés | `tenants.id` |
| `agent_runs` | Exécutions d'agents | `agents.id`, `tenants.id` |
| `agent_spans` | Spans (chaînes, LLM, outils) | `agent_runs.id`, `tenants.id` |
| `anomalies` | Anomalies détectées | `agent_runs.id`, `tenants.id` |
| `alerts` | Alertes de seuil | `tenants.id`, `agents.id` |
| `audit_logs` | Journal d'audit | `tenants.id` |

## Stack technique

| Couche | Technologie |
|--------|-------------|
| Runtime | Python 3.11+ |
| API | FastAPI + Uvicorn |
| Base de données | PostgreSQL 16 (asyncpg) |
| Cache / Queue | Redis 7 |
| Workers | Celery 5.4 |
| Dashboard | Streamlit + Plotly |
| Monitoring | Grafana |
| Conteneurisation | Docker + docker-compose |
| SDK | httpx + LangGraph |
| CI/CD | GitHub Actions |
