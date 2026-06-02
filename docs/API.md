# API REST — Documentation Technique

Base URL : `http://localhost:8000`

Version : `0.1.0`

Tous les endpoints (sauf `/health` et `/api/v1/tenants`) nécessitent une authentification.

---

## Health

### `GET /health`
Vérification de l'état du service.

**Réponse 200 :**
```json
{"status": "ok", "version": "0.1.0", "timestamp": "2026-06-02T10:00:00"}
```

---

## Tenants (multi-tenant)

### `POST /api/v1/tenants`
Créer un nouveau locataire. **Ne nécessite pas d'authentification.**

**Corps :**
| Champ | Type | Contraintes |
|-------|------|-------------|
| `name` | string | 1-255 caractères, unique |
| `slug` | string | 1-255 caractères, `^[a-z0-9-]+$`, unique |
| `api_key` | string | 16-128 caractères |

**Réponse 201 :**
```json
{
  "id": "uuid",
  "name": "mon-tenant",
  "slug": "mon-tenant",
  "plan": "free",
  "is_active": true,
  "created_at": "2026-06-02T10:00:00+00:00"
}
```

**Erreurs :** `409 Conflict` — slug déjà existant.

---

## Auth

### `POST /api/v1/auth/token`
Générer un JWT Bearer à partir d'une API Key.

**Headers :** `X-API-Key: <api_key>`

**Réponse 200 :**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "tenant_id": "uuid"
}
```

Le JWT expire après 1440 minutes (24h). Configuration : `AGENT_OBS_ACCESS_TOKEN_EXPIRE_MINUTES`.

---

## Agents

### `POST /api/v1/agents`
Enregistrer un nouvel agent. Si un agent avec le même nom existe déjà, met à jour sa version.

**Headers :** `X-API-Key: <api_key>` ou `Authorization: Bearer <jwt>`

**Corps :**
| Champ | Type | Défaut |
|-------|------|--------|
| `name` | string (1-255) | — |
| `version` | string (1-50) | — |
| `langgraph_version` | string | `""` |

**Réponse 201 :**
```json
{
  "id": "uuid",
  "name": "research-agent",
  "version": "1.0.0",
  "langgraph_version": "0.2.60",
  "is_active": true,
  "created_at": "2026-06-02T10:00:00+00:00"
}
```

### `GET /api/v1/agents`
Lister tous les agents du tenant authentifié.

**Headers :** `X-API-Key: <api_key>` ou `Authorization: Bearer <jwt>`

**Réponse 200 :**
```json
[
  {
    "id": "uuid",
    "name": "research-agent",
    "version": "1.0.0",
    "langgraph_version": "0.2.60",
    "is_active": true,
    "created_at": "2026-06-02T10:00:00+00:00"
  }
]
```

---

## Ingestion

### `POST /api/v1/ingest`
Ingérer une exécution d'agent (run) avec ses spans.

**Headers :** `X-API-Key: <api_key>` (API Key uniquement, pas de Bearer)

**Corps :**
| Champ | Type | Défaut |
|-------|------|--------|
| `agent_id` | string (uuid) | — |
| `session_id` | string \| null | null |
| `input_preview` | string \| null | null |
| `output_preview` | string \| null | null |
| `duration_ms` | int \| null | null |
| `total_tokens` | int \| null | null |
| `prompt_tokens` | int \| null | null |
| `completion_tokens` | int \| null | null |
| `cost_usd` | float \| null | null |
| `status` | string | `"completed"` |
| `error` | string \| null | null |
| `metadata` | dict \| null | null |
| `spans` | list[SpanPayload] \| null | null |

**SpanPayload :**
| Champ | Type | Défaut |
|-------|------|--------|
| `parent_span_id` | string \| null | null |
| `span_type` | string | — |
| `span_name` | string | — |
| `input_data` | dict \| null | null |
| `output_data` | dict \| null | null |
| `duration_ms` | int \| null | null |
| `tokens_used` | int \| null | null |
| `cost_usd` | float \| null | null |
| `status` | string | `"success"` |
| `error` | string \| null | null |

**Réponse 200 :**
```json
{"run_id": "uuid", "status": "completed"}
```

**Erreurs :** `404 Not Found` — agent_id inconnu.

---

## Métriques

### `GET /api/v1/metrics/{agent_id}`
Agrégations de performance pour un agent.

**Query :**
| Paramètre | Type | Défaut |
|-----------|------|--------|
| `since` | string | `"24h"` |

Valeurs supportées pour `since` : `1h`, `6h`, `24h`, `7d`, `30d`.

**Réponse 200 :**
```json
{
  "total_runs": 150,
  "avg_duration_ms": 1234.56,
  "total_tokens": 50000,
  "total_cost_usd": 0.05,
  "error_count": 3,
  "success_count": 147,
  "period_hours": "24h"
}
```

---

## Traces

### `GET /api/v1/traces/{agent_id}`
Historique des exécutions d'un agent.

**Query :**
| Paramètre | Type | Défaut | Max |
|-----------|------|--------|-----|
| `limit` | int | 50 | 500 |
| `offset` | int | 0 | — |

**Réponse 200 :**
```json
[
  {
    "id": "uuid",
    "session_id": "session-123",
    "input_preview": "...",
    "output_preview": "...",
    "duration_ms": 1500,
    "total_tokens": 500,
    "cost_usd": 0.001,
    "status": "completed",
    "error": null,
    "created_at": "2026-06-02T10:00:00+00:00"
  }
]
```

---

## Anomalies

### `GET /api/v1/anomalies/{agent_id}`
Anomalies non résolues pour un agent.

**Query :**
| Paramètre | Type | Défaut | Max |
|-----------|------|--------|-----|
| `limit` | int | 50 | 500 |

**Réponse 200 :**
```json
[
  {
    "id": "uuid",
    "run_id": "uuid",
    "anomaly_type": "hallucination",
    "severity": "high",
    "title": "Hallucination potentielle détectée",
    "description": "...",
    "evidence": {"is_hallucination": true, "confidence": 0.95},
    "is_resolved": false,
    "created_at": "2026-06-02T10:00:00+00:00"
  }
]
```

Types d'anomalies : `hallucination`, `infinite_loop`,
Sévérités : `low`, `medium`, `high`, `critical`.

---

## Alertes

### `GET /api/v1/alerts`
Alertes actives (status `firing`).

**Query :**
| Paramètre | Type | Défaut | Max |
|-----------|------|--------|-----|
| `limit` | int | 50 | 500 |

**Réponse 200 :**
```json
[
  {
    "id": "uuid",
    "rule_name": "high_error_rate",
    "metric": "error_rate",
    "threshold": 0.1,
    "current_value": 0.25,
    "status": "firing",
    "created_at": "2026-06-02T10:00:00+00:00"
  }
]
```

---

## Dashboard

### `GET /api/v1/dashboard`
Statistiques globales du tableau de bord.

**Query :**
| Paramètre | Type | Défaut |
|-----------|------|--------|
| `since` | string | `"24h"` |

**Réponse 200 :**
```json
{
  "total_runs": 1500,
  "total_tokens": 500000,
  "total_cost_usd": 0.50,
  "avg_duration_ms": 1234.56,
  "errors": 15,
  "active_anomalies": 3,
  "active_agents": 5
}
```

---

## Coûts

### `GET /api/v1/costs`
Rapport de coûts par agent.

**Query :**
| Paramètre | Type | Défaut |
|-----------|------|--------|
| `since` | string | `"30d"` |

**Réponse 200 :**
```json
[
  {
    "agent_name": "research-agent",
    "agent_id": "uuid",
    "runs": 500,
    "total_cost_usd": 0.25,
    "total_tokens": 250000,
    "avg_duration_ms": 1500.0
  }
]
```

---

## Codes d'erreur

| Statut | Signification |
|--------|---------------|
| 201 | Créé |
| 401 | Non authentifié — clé API manquante, invalide, ou JWT expiré |
| 404 | Ressource non trouvée |
| 409 | Conflit (tenant déjà existant) |
| 422 | Erreur de validation (Pydantic) |
| 500 | Erreur interne |

## Authentification

### API Key
```
X-API-Key: votre-clé-api
```

### Bearer JWT
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

Le JWT s'obtient via `POST /api/v1/auth/token` avec une API Key valide (header `X-API-Key`). Les endpoints read (`GET`) acceptent les deux modes ; l'ingestion (`POST /api/v1/ingest`) n'accepte que l'API Key.
