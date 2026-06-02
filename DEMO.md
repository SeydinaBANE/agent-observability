# Démo Agent Observability

## 1. Prérequis

- Docker Desktop (postgres + redis)
- Python 3.11+
- Optionnel : clé OpenAI ou OpenRouter pour la détection d'hallucinations

## 2. Démarrage rapide

```bash
# Tout en une commande
./dev-cli.py start
```

Le CLI lance automatiquement :
- postgres + redis (Docker)
- API FastAPI sur http://localhost:8000
- Dashboard Streamlit sur http://localhost:8501
- Documentation interactive sur http://localhost:8000/docs

Pour arrêter :
```bash
./dev-cli.py stop
```

## 3. Seeder des données de démonstration

```bash
./dev-cli.py seed
```

Crée :
- **1 tenant** `demo` (clé API : `demo-key-local-dev`)
- **3 agents** : `customer-support`, `code-reviewer`, `data-analyzer`
- **15 runs** par agent avec stats variées

## 4. Explorer le dashboard

Ouvrir http://localhost:8501

### Onglets

| Onglet | Description |
|---|---|
| 📊 Métriques | Coût et tokens par agent (graphiques barres) |
| 🔄 Traces | Dernières 50 runs avec sélecteur d'agent |
| ⚠️ Anomalies | Hallucinations et boucles infinies détectées |
| 🔔 Alertes | Alertes actives |
| 💰 Coûts | Rapport détaillé + camembert de répartition |

## 5. Tester l'API manuellement

```bash
# 1. Health
curl http://localhost:8000/health

# 2. Créer un agent
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-local-dev" \
  -d '{"name":"mon-agent","version":"1.0.0"}'

# 3. Lister les agents
curl http://localhost:8000/api/v1/agents \
  -H "X-API-Key: demo-key-local-dev"

# 4. Ingérer un run
AGENT_ID=<id récupéré ci-dessus>
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-local-dev" \
  -d "{\"agent_id\":\"$AGENT_ID\",\"duration_ms\":1500,\"total_tokens\":500,\"cost_usd\":0.001,\"status\":\"completed\"}"

# 5. Stats dashboard
curl "http://localhost:8000/api/v1/dashboard" \
  -H "X-API-Key: demo-key-local-dev"

# 6. Métriques agent
curl "http://localhost:8000/api/v1/metrics/$AGENT_ID" \
  -H "X-API-Key: demo-key-local-dev"
```

## 6. Authentification JWT

```bash
# Obtenir un token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -H "X-API-Key: demo-key-local-dev" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Utiliser le token (Authorization Bearer)
curl http://localhost:8000/api/v1/dashboard \
  -H "Authorization: Bearer $TOKEN"
```

## 7. Détection d'anomalies

Avec une clé OpenAI configurée dans `.env` :
```bash
AGENT_OBS_OPENAI_API_KEY=sk-...
```

1. Ingérer un run avec un input/output incohérent
2. Le worker Celery `analyze_run` détecte les hallucinations et boucles infinies
3. Les anomalies apparaissent dans l'onglet ⚠️ du dashboard
4. Voir les workers :
```bash
docker compose logs worker -f
```

## 8. Tester le SDK

```bash
pip install -e sdk/
```

```python
from agent_obs_sdk import AgentObservabilityClient

client = AgentObservabilityClient(
    api_key="demo-key-local-dev",
    base_url="http://localhost:8000",
)

@client.monitor(agent_id="mon-agent", session_id="demo-1")
def hello():
    return "Hello world"

hello()
```

## 9. Démo Docker (stack complète)

```bash
# Build + start tout
make docker-prod-up

# Voir les logs
docker compose logs -f

# Arrêter
make docker-prod-down
```

## Parcours recommandé (5 min)

1. `./dev-cli.py start` → attendre "Tout est lancé"
2. `./dev-cli.py seed` → injecter les données
3. Ouvrir http://localhost:8501 → survoler les 5 onglets
4. `curl http://localhost:8000/api/v1/dashboard` → vérifier l'API
5. `./dev-cli.py health` → tout est vert
6. `./dev-cli.py stop` → cleanup
