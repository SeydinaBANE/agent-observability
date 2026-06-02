# Guide de Développement

## Prérequis

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 16 (via Docker)
- Redis 7 (via Docker)

## Setup rapide

```bash
# 1. Cloner le dépôt
git clone <url>
cd agent-observability

# 2. Installer les dépendances
pip install -e ".[dev,dashboard,workers]"
pip install -e sdk/

# 3. Démarrer PostgreSQL et Redis
make test-services

# 4. Lancer les tests
make test
```

## Structure du projet

```
agent-observability/
├── api/              # API REST FastAPI (11 endpoints)
│   ├── auth.py       # Authentification (API Key + JWT, fallback automatique)
│   └── main.py       # Routes, CORS, startup (seed auto ON CONFLICT)
├── core/             # Couche métier
│   ├── config.py     # Configuration (pydantic-settings, extra="ignore")
│   ├── database.py   # Connexion PostgreSQL (asyncpg)
│   ├── models.py     # Modèles SQLAlchemy (7 tables)
│   └── schemas.py    # Schémas Pydantic
├── workers/          # Workers Celery
│   ├── celery_app.py # Configuration Celery
│   ├── detectors.py  # Détection d'anomalies
│   └── tasks.py      # Tâches asynchrones
├── sdk/              # SDK Python (agent-obs-sdk)
│   └── agent_obs/
│       ├── client.py # Client HTTP + décorateur
│       └── langgraph_callback.py # Callback LangGraph
├── dashboard/        # Dashboard Streamlit (5 onglets)
│   └── app.py
├── tests/            # Tests (15 tests : 8 API, 2 détection, 5 SDK)
│   ├── conftest.py   # Fixtures (DB, client HTTP)
│   ├── test_api.py   # Tests API
│   ├── test_detectors.py # Tests détection
│   └── test_sdk.py   # Tests SDK
├── grafana/          # Dashboards Grafana
├── dev-cli.py        # CLI tout-en-un (11 commandes, zéro dépendance)
├── .env              # Fichier de configuration
└── Makefile
```

## Commandes Make

| Commande | Description |
|----------|-------------|
| `make install` | Créer venv + installer toutes les dépendances |
| `make lint` | Vérifie le code (ruff + mypy) |
| `make format` | Formate le code (ruff --fix + ruff format) |
| `make typecheck` | Vérifie les types (mypy) |
| `make test` | Exécute les tests avec couverture (project name isolé) |
| `make ci` | Pipeline CI complet (lint + test) |
| `make test-services` | Démarre PostgreSQL + Redis (projet `agent-observability-test`) |
| `make docker-up` | Stack complète en mode dev (docker-compose.dev.yml) |
| `make docker-prod-up` | Stack complète en mode production |
| `make build` | Build des wheels pip |

## Tests

### Exécution

```bash
make test              # Tous les tests (project name isolé)
pytest tests/ -v       # Mode verbeux
pytest tests/test_api.py -v --no-header  # Fichier spécifique
```

Les tests utilisent `-p agent-observability-test` pour Docker, garantissant l'isolation avec la stack de production.

### Fixtures disponibles

| Fixture | Portée | Description |
|---------|--------|-------------|
| `setup_database` | session | Crée/supprime les tables |
| `db_session` | function | Session SQLAlchemy |
| `client` | function | Client HTTP AsyncClient |
| `test_tenant` | function | Tenant de test avec clé API |
| `api_key` | function | Clé API de test (`test-key-12345678`) |

### Conventions

- Nommage : `test_<fonction>_<cas>` (ex: `test_create_tenant_duplicate`)
- Une fixture `test_tenant` crée un tenant avec clé `test-key-12345678`
- Les tests API utilisent `headers={"X-API-Key": "test-key-12345678"}`
- 15 tests : 8 API, 2 détection, 5 SDK

## Linting et Formatage

```bash
make lint          # ruff check + ruff format --check + mypy
make format        # ruff --fix + ruff format
make typecheck     # mypy
```

Configuration dans `pyproject.toml` :
- Line length : 130
- Target : Python 3.11
- Quotes : doubles
- Sélecteurs : E, F, I, N, W, UP, RUF

## Bonnes pratiques

### Base de données
- Les migrations sont gérées par SQLAlchemy `create_all()`
- En production, utiliser Alembic pour les migrations
- La table `agent_runs.metadata` est renommée `run_metadata` pour éviter le conflit avec `DeclarativeBase.metadata`

### Authentification
- Dépendances FastAPI : `get_tenant_from_api_key`, `_get_tenant_from_api_key_optional`, `get_tenant_from_bearer`, `get_authenticated_tenant`
- `get_authenticated_tenant` essaie d'abord l'API Key, puis le Bearer, avant de lever 401
- L'ingestion (`POST /api/v1/ingest`) utilise `get_tenant_from_api_key` (API Key uniquement)

### Workers
- Les tâches Celery sont définies dans `workers/tasks.py`
- Les détecteurs sont dans `workers/detectors.py` (fonctions async pures)
- La purge des traces utilise SQLAlchemy synchrone (pas de session async)

### SDK
- Package séparé avec son propre `pyproject.toml`
- Installé en mode editable : `pip install -e sdk/`
- Le décorateur `@monitor` supporte fonctions sync et async

## CI/CD

Pipeline GitHub Actions (`.github/workflows/ci.yml`) :

1. **precheck** : vérification des clés API
2. **lint** : ruff check + ruff format --check + mypy
3. **test** : pytest avec PostgreSQL + Redis (project name isolé)
4. **precommit** : pre-commit run --all-files
5. **security** : bandit + trivy
6. **docker** : build multi-stage
7. **deploy** : déploiement (optionnel)
