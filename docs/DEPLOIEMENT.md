# Guide de Déploiement

## Architecture de déploiement

```
                    ┌─────────────┐
                    │   Traefik    │  (proxy inverse, TLS, rate limiting)
                    │   :443       │
                    └──────┬──────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
    ┌───────▼──────┐ ┌────▼────┐ ┌───────▼──────┐
    │   API        │ │Dashboard│ │   Workers    │
    │  (FastAPI)   │ │Streamlit│ │  (Celery)    │
    │    :8000     │ │  :8501  │ │              │
    └───────┬──────┘ └─────────┘ └───────┬──────┘
            │                            │
    ┌───────▼──────┐            ┌───────▼──────┐
    │  PostgreSQL  │            │    Redis     │
    │    :5432     │            │    :6379     │
    └──────────────┘            └──────────────┘
```

## Docker Compose (Production)

### docker-compose.yml

Le fichier `docker-compose.yml` contient 7 services :

| Service | Image | Port | Dépend de |
|---------|-------|------|-----------|
| `traefik` | traefik:v3.1 | 80, 443 | — |
| `postgres` | timescale/timescaledb:latest-pg16 | 5432 | — |
| `redis` | redis:7-alpine | 6379 | — |
| `api` | agent-observability-api:latest | — | postgres, redis |
| `dashboard` | agent-observability-dashboard:latest | — | api |
| `worker` | agent-observability-worker:latest | — | postgres, redis |
| `beat` | agent-observability-beat:latest | — | redis |

### Déploiement

```bash
# 1. Configurer les variables d'environnement
# .env est chargé automatiquement par docker-compose
# Éditer .env avec vos valeurs de production

# 2. Build et démarrer
make docker-prod-up

# 3. Vérifier l'état
docker compose ps
curl http://localhost/health

# 4. Consulter les logs
docker compose logs -f api
docker compose logs -f worker
```

### Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `AGENT_OBS_DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@postgres:5432/agent_obs` | URL PostgreSQL |
| `AGENT_OBS_REDIS_URL` | `redis://redis:6379/0` | URL Redis |
| `AGENT_OBS_SECRET_KEY` | `change-me-in-production` | Clé secrète JWT |
| `AGENT_OBS_DEMO_API_KEY` | `demo-key-local-dev` | Clé API du tenant démo (seed automatique) |
| `AGENT_OBS_DASHBOARD_API_KEY` | `demo-key-local-dev` | Clé API par défaut du dashboard |
| `AGENT_OBS_OPENAI_API_KEY` | `""` | Clé API OpenAI pour détection |
| `AGENT_OBS_OPENROUTER_API_KEY` | `""` | Clé API OpenRouter (alternative) |
| `AGENT_OBS_ENVIRONMENT` | `development` | `production` en prod |
| `AGENT_OBS_SENTRY_DSN` | `""` | DSN Sentry pour tracing |

## Dockerfile (Multi-stage)

Le `Dockerfile` définit 4 cibles :

```bash
docker compose build api           # Cible api — FastAPI sur :8000
docker compose build dashboard     # Cible dashboard — Streamlit sur :8501
docker compose build worker        # Cible worker — Celery
docker compose build beat          # Cible beat — Celery Beat scheduler
```

**Étapes :**
1. `base` : Python 3.12-slim, dépendances système, bcrypt<5.0 pour compatibilité passlib
2. `api` : FastAPI + Uvicorn
3. `dashboard` : Streamlit
4. `worker` + `beat` : Celery

**Notes :** Le Dockerfile n'installe pas `curl`/`ca-certificates` (base `slim` suffit), et exclut les extras `[dev]` des images de production.

## Dev Docker Compose

`docker-compose.dev.yml` pour le développement avec hot-reload :

```bash
make test-services    # Démarre postgres + redis (project name: agent-observability-test)
make api              # uvicorn --reload + services
make dev              # api + dashboard
```

Les conteneurs de test sont isolés via `-p agent-observability-test` pour ne pas impacter la stack de production.

## CI/CD Pipeline

Le workflow GitHub Actions (`.github/workflows/ci.yml`) automatisé :

```yaml
jobs:
  lint, format, typecheck, test, security    # Check qualité
  precheck:                                  # Gate conditionnelle
    needs: [lint, format, typecheck, test]
  docker-build:                              # Build et push images
    needs: [precheck]
  trivy-scan:                                # Scan vulnérabilités
    needs: [docker-build]
  deploy:                                    # Déploiement
    needs: [trivy-scan]
    if: github.ref == 'refs/heads/main'
```

Le déploiement nécessite les secrets GitHub :
- `DOCKER_USERNAME` / `DOCKER_PASSWORD` : Registry Docker
- `SSH_PRIVATE_KEY` / `SSH_HOST` : Serveur de déploiement

## Monitoring

### Grafana

Dashboards pré-configurés dans `grafana/` :

```bash
# Démarrer Grafana (manuellement)
docker run -d --name grafana \
  -p 3000:3000 \
  -v ./grafana:/var/lib/grafana/dashboards \
  grafana/grafana:latest
```

Données sources recommandées : PostgreSQL (via datasource).

### Health check

```bash
curl http://localhost/health
# {"status":"ok","version":"0.1.0","timestamp":"..."}
```

## Sécurité

- **Clé API** : hachée avec bcrypt (jamais stockée en clair), `bcrypt>=4.0,<5.0` pour compatibilité
- **JWT** : signé avec HS256, durée configurable
- **CORS** : `allow_origins=["*"]` par défaut, restreindre en production
- **PostgreSQL** : écoute uniquement sur le réseau Docker en prod
- **Traefik** : TLS/SSL, rate limiting
- **Startup safe** : seed auto via `ON CONFLICT (name) DO NOTHING` (pas de crash multi-worker)
- **Docker** : images basées sur `python:3.12-slim`, scan Trivy dans CI
- **Dépendances** : Dependabot (pip, Docker, GitHub Actions), pip-audit dans CI

## Sauvegarde

```bash
# Backup PostgreSQL
docker compose exec postgres pg_dump -U postgres agent_obs > backup.sql

# Restore
docker compose exec -T postgres psql -U postgres agent_obs < backup.sql
```

## Dépannage

### L'API ne démarre pas
```bash
docker compose logs api
# Vérifier que postgres est accessible
docker compose exec api python -c "import asyncpg; asyncpg.connect('...')"
```

### Les workers ne traitent pas les tâches
```bash
docker compose logs worker
# Vérifier Redis
docker compose exec redis redis-cli ping  # doit répondre PONG
```

### Erreur de connexion PostgreSQL
```bash
# Tester la connexion
docker compose exec postgres psql -U postgres -d agent_obs -c "SELECT 1"
```

### Port déjà utilisé
```bash
# Changer les ports dans .env ou docker-compose.yml
# Vérifier les processus
lsof -i :8000
```
