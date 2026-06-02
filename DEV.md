# DEV.md — Guide de développement

## Stack

- **API** : FastAPI + uvicorn (hot-reload, 11 endpoints)
- **Base** : PostgreSQL 16 (TimescaleDB) + Redis 7
- **Async** : SQLAlchemy 2.x async + asyncpg
- **Tâches** : Celery (broker Redis)
- **Dashboard** : Streamlit
- **Auth** : API Key (X-API-Key) + JWT Bearer (fallback automatique)
- **LLM** : OpenAI / OpenRouter / Ollama pour détection d'hallucinations

## Setup

```bash
git clone <url> && cd agent-observability
pip install -e ".[dev,dashboard,workers]" && pip install -e sdk/
cp .env.example .env   # éditer si besoin
```

## Workflow quotidien

```bash
# Démarrer l'environnement de dev complet
./dev-cli.py start     # postgres + redis + API (:8000) + dashboard (:8501)

# Ou séparément
make api               # postgres + redis + API seulement
make dashboard         # dashboard seulement (API doit déjà tourner)

# Seed des données de démo
./dev-cli.py seed

# Lancer les tests
./dev-cli.py test                 # tous les tests
./dev-cli.py test --coverage      # avec rapport de couverture
./dev-cli.py test -f tests/test_api.py -k "test_health"  # test filtré

# Lint
./dev-cli.py lint                 # ruff + mypy

# CI complète
./dev-cli.py ci
```

## Structure du code

```
api/main.py        # 11 endpoints REST + startup (seed auto tenant demo, ON CONFLICT)
api/auth.py        # hash/verify API key, JWT create/decode, dépendances FastAPI
core/config.py     # Settings pydantic (préfixe AGENT_OBS_, extra="ignore")
core/models.py     # 7 modèles SQLAlchemy (Tenant → Agent → Run → Span/Anomaly)
core/schemas.py    # Pydantic request/response
core/database.py   # engine async + get_db
workers/tasks.py   # Celery : analyze_run, purge_old_traces
workers/detectors.py  # detect_loops, detect_hallucinations (LLM-as-judge)
dashboard/app.py   # Streamlit 5 onglets
sdk/               # package pip séparé (agent-obs-sdk)
dev-cli.py         # CLI tout-en-un (11 commandes, zéro dépendance)
.env               # Fichier de configuration (chargé automatiquement)
```

## Conventions

- **Langue** : code + commentaires en anglais, docs utilisateur en français
- **Lint** : `ruff` (line-length 130), `mypy` strict sur `api/ core/ workers/`
- **Tests** : pytest asyncio, PostgreSQL réel (pas de mock), 1 fixture tenant + agent
- **Commits** : préfixes `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
- **Env vars** : préfixe `AGENT_OBS_`, defaults dans `core/config.py`, `.env` chargé automatiquement, `extra="ignore"` pour tolérer les vars inconnues
- **Auth** : endpoints d'ingestion = API Key uniquement, endpoints read = API Key ou Bearer (fallback via `_get_tenant_from_api_key_optional`)

## Commandes utiles

```bash
make format         # ruff --fix + ruff format
make typecheck      # mypy uniquement
make test-quick     # pytest -x (stop au premier échec)
./dev-cli.py logs api   # logs de l'API uniquement
./dev-cli.py reset --force  # vide la base
./dev-cli.py health      # vérifie que tout tourne
```
