# PROD.md — Production Deployment

## Architecture de production

```
Client (SDK) ──► Traefik (:443) ──► API (:8000) ──► PostgreSQL (TimescaleDB)
                                                    ──► Redis
                                 ──► Dashboard (:8501)
                                 ──► Worker (Celery)
                                 ──► Beat (cron)
```

7 services : `traefik`, `postgres`, `redis`, `api`, `dashboard`, `worker`, `beat`.

## Prérequis

- Domaine avec DNS pointant vers le serveur
- Docker & Docker Compose (ou Docker Swarm / Kubernetes)
- PostgreSQL 16+ (TimescaleDB recommandé)
- Redis 7+
- Clé API OpenAI ou OpenRouter (pour détection d'hallucinations)

## Déploiement avec Docker Compose

```bash
# 1. Cloner
git clone <url> && cd agent-observability

# 2. Configuration (`.env` chargé automatiquement)
# Éditer .env avec les valeurs de production

# 3. Lancer
docker compose up -d --build
```

## Variables d'environnement critiques

```bash
# OBLIGATOIRE
AGENT_OBS_SECRET_KEY=<clé forte 32+ caractères>

# BASE DE DONNÉES
AGENT_OBS_DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/agent_obs

# CLÉ API DÉMO (créée automatiquement au démarrage si aucun tenant n'existe)
AGENT_OBS_DEMO_API_KEY=demo-key-local-dev

# LLM JUDGE (pour anomalies)
AGENT_OBS_OPENAI_API_KEY=sk-...         # OpenAI
# ou
AGENT_OBS_OPENROUTER_API_KEY=sk-or-...  # OpenRouter

# DASHBOARD
AGENT_OBS_DASHBOARD_API_KEY=demo-key-local-dev

# RÉTENTION
AGENT_OBS_RETENTION_DAYS_RAW=7
AGENT_OBS_RETENTION_DAYS_AGGREGATED=90

# SENTRY
AGENT_OBS_SENTRY_DSN=https://...
```

## Sécurité

| Risque | Mitigation |
|---|---|
| API key leak | Rate limiting + rotation régulière + audit.log |
| JWT volé | `access_token_expire_minutes=60`, TLS only |
| Injection SQL | SQLAlchemy ORM (pas de raw SQL) |
| CORS | `allow_origins=["*"]` par défaut, restreindre en prod |
| Rétention | `purge_old_traces` quotidien (Celery Beat) |
| Startup safe | Seed tenant via `ON CONFLICT (name) DO NOTHING` |

## Monitoring

- **Sentry** : configurer `AGENT_OBS_SENTRY_DSN` pour les erreurs API
- **Grafana** : dashboards fournis dans `grafana/`
- **Health check** : `GET /health` (utiliser comme probe Docker)
- **Logs** : `docker compose logs -f api worker beat`

## Sauvegarde

```bash
# Backup PostgreSQL
docker exec agent-observability-postgres-1 pg_dump -U postgres agent_obs > backup_$(date +%Y%m%d).sql

# Restore
cat backup.sql | docker exec -i agent-observability-postgres-1 psql -U postgres agent_obs
```

## Scaling

```bash
# Plus de workers Celery
docker compose up -d --scale worker=3 --no-deps worker

# Read replicas PostgreSQL (configurer DATABASE_URL secondaire)
```

## TLS (Let's Encrypt)

Traefik gère automatiquement les certificats via le provider Let's Encrypt. Configurer dans `docker-compose.yml` :

```yaml
- "--certificatesresolvers.letsencrypt.acme.email=admin@example.com"
```

## Checklist mise en production

- [ ] `AGENT_OBS_SECRET_KEY` changée (32+ caractères aléatoires)
- [ ] `AGENT_OBS_ENVIRONMENT=production`
- [ ] Clé API OpenAI/OpenRouter configurée
- [ ] Domaine + DNS + TLS (Traefik)
- [ ] Backup PostgreSQL automatisé
- [ ] Monitoring (Sentry + Grafana)
- [ ] Rate limiting configuré
- [ ] CORS restreint aux origines autorisées
- [ ] Logs centralisés (optionnel : Loki + Grafana)
