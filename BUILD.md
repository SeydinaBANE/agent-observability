# BUILD.md — Build & Packaging

## Build pip

```bash
# Builder les wheels
make build
# → dist/agent_observability-0.1.0-py3-none-any.whl
# → dist/agent_obs_sdk-0.1.0-py3-none-any.whl

# Installer depuis la wheel
pip install dist/agent_observability-0.1.0-py3-none-any.whl
pip install dist/agent_obs_sdk-0.1.0-py3-none-any.whl
```

## Build Docker

```bash
# Build toutes les images
make docker-build

# Build une image spécifique
docker compose build api
docker compose build dashboard
docker compose build worker
docker compose build beat

# Voir les tags générés
docker images "agent-observability-*"
```

Les images Docker sont multi-stage (`Dockerfile`) :

| Cible | Base | Contenu |
|---|---|---|
| `api` | python:3.12-slim | FastAPI + uvicorn |
| `dashboard` | python:3.12-slim | Streamlit |
| `worker` | python:3.12-slim | Celery worker |
| `beat` | python:3.12-slim | Celery beat scheduler |

### Particularités du Dockerfile

- Pas d'`apt-get install curl/ca-certificates` (base `slim` suffit)
- Les extras `.[dev]` sont exclus des images de production
- Le SDK (`sdk/`) est installé via `pip install -e sdk/`
- `bcrypt>=4.0,<5.0` dans `pyproject.toml` pour compatibilité avec `passlib`

## CI/CD (GitHub Actions)

Le pipeline `.github/workflows/ci.yml` exécute :

1. **precheck** — vérifie que les clés API ne fuient pas
2. **lint** — ruff check + ruff format + mypy
3. **test** — pytest avec PostgreSQL réel (service Docker, project name isolé)
4. **precommit** — pre-commit run --all-files
5. **security** — bandit + trivy (scan de vulnérabilités)
6. **docker-build** — build et push des images
7. **deploy** — déploiement (optionnel)

Déclencheurs : push sur `main`, PR vers `main`, manuel (workflow_dispatch).

## Versionnement

```
VERSION = 0.1.0
         │││
         ││└── patch (bugfix, backward-compatible)
         │└── minor (nouvelle feature, backward-compatible)
         └── major (breaking changes)
```

Bump via `make bump-patch`, `make bump-minor`, `make bump-major` (édite `pyproject.toml` et les setup.cfg).

## Dépendances

```bash
# Vérifier les dépendances obsolètes
pip list --outdated

# Mettre à jour une dépendance
pip install <package> --upgrade

# Générer un lock file
pip freeze > requirements.lock
```
