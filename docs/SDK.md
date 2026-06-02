# SDK Python — agent-obs-sdk

Package d'observabilité pour agents LangGraph. Permet d'instrumenter vos agents et d'envoyer les traces à la plateforme Agent Observability Dashboard.

## Installation

```bash
pip install agent-obs-sdk
```

Ou en mode développement depuis le dépôt :

```bash
pip install -e sdk/
```

## Configuration

Variables d'environnement :

| Variable | Défaut | Description |
|----------|--------|-------------|
| `AGENT_OBS_URL` | `http://localhost:8000` | URL de l'API |
| `AGENT_OBS_API_KEY` | `""` | Clé API du tenant |
| `AGENT_OBS_AGENT_ID` | `""` | ID de l'agent par défaut |

---

## Client HTTP

### AgentObservabilityClient

```python
from agent_obs import AgentObservabilityClient

client = AgentObservabilityClient(
    base_url="http://localhost:8000",
    api_key="ta-clé-api",
    agent_id="mon-agent-id",
)
```

**Paramètres du constructeur :**

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `base_url` | str \| None | `AGENT_OBS_URL` | URL de l'API |
| `api_key` | str \| None | `AGENT_OBS_API_KEY` | Clé API |
| `agent_id` | str \| None | `AGENT_OBS_AGENT_ID` | ID agent par défaut |
| `timeout` | float | `10.0` | Timeout HTTP (s) |
| `max_retries` | int | `3` | Nombre de tentatives |
| `batch_size` | int | `10` | Taille de lot |

### `client.set_session(session_id)`
Définit un ID de session pour grouper les runs.

### `client.record_run(...)`
Enregistre une exécution d'agent.

```python
result = client.record_run(
    agent_id="uuid",
    input_preview="Quelle est la capitale de la France ?",
    output_preview="La capitale de la France est Paris.",
    duration_ms=1500,
    total_tokens=500,
    prompt_tokens=400,
    completion_tokens=100,
    cost_usd=0.001,
    status="completed",
    spans=[...],
)
```

### `client.record_error(agent_id, error, metadata)`
Enregistre une exécution en échec.

### `client.close()`
Ferme la session HTTP.

---

## Décorateur @monitor

Instrumente automatiquement une fonction : capture la durée, les entrées/sorties, et détecte les erreurs.

```python
from agent_obs import monitor

@monitor(agent_id="mon-agent", api_key="ta-clé-api")
async def mon_agent_llm(question: str) -> str:
    # ... logique LLM ...
    return réponse
```

Le décorateur supporte les fonctions **synchrone et asynchrone**. Il envoie automatiquement un run à chaque appel avec le statut `completed` ou `error`.

---

## Callback LangGraph

### ObservabilityCallback

Callback LangChain/LangGraph qui capture automatiquement les chaînes, appels LLM, et appels d'outils.

```python
from agent_obs import AgentObservabilityClient, ObservabilityCallback
from langgraph.graph import StateGraph

client = AgentObservabilityClient(api_key="ta-clé-api")
callback = ObservabilityCallback(client)

# Utilisation avec LangGraph
builder = StateGraph(MonState)
builder.add_node("node1", mon_agent)
graph = builder.compile()
result = graph.invoke(
    {"input": "question"},
    {"callbacks": [callback]}
)

# Envoi des spans accumulés
callback.flush(
    input_preview="question",
    output_preview=str(result)[:500]
)
```

**Méthodes du callback :**

| Méthode | Déclencheur |
|---------|-------------|
| `on_chain_start` | Début d'une chaîne LangChain |
| `on_chain_end` | Fin d'une chaîne |
| `on_chain_error` | Erreur dans une chaîne |
| `on_llm_start` | Début d'un appel LLM |
| `on_llm_end` | Fin d'un appel LLM |
| `on_tool_start` | Début d'un appel d'outil |
| `on_tool_end` | Fin d'un appel d'outil |
| `flush()` | Envoie tous les spans accumulés |

**Structure des spans :**

```
Session
  └── Run (agent_id, session_id, durée, tokens, coût)
       ├── Span: chain (appel principal)
       │    ├── Span: llm_call (appel GPT-4o-mini, tokens, coût)
       │    └── Span: tool (appel API, résultat)
       └── Span: chain (réponse finale)
```

---

## SpanData

Structure de données pour les spans individuels :

```python
from agent_obs import SpanData

SpanData(
    parent_span_id=None,       # UUID du span parent (None = racine)
    span_type="llm_call",      # chain | llm_call | tool
    span_name="gpt-4o-mini",   # Nom du span
    input_data={"prompt": ...},# Données d'entrée
    output_data={"response": ...}, # Données de sortie
    duration_ms=1200,          # Durée en ms
    tokens_used=500,           # Tokens consommés
    cost_usd=0.001,            # Coût en USD
    status="success",          # success | error
    error=None,                # Message d'erreur
)
```

## Gestion des erreurs

Le client réessaie automatiquement jusqu'à `max_retries` fois avec backoff exponentiel (2^tentative secondes). En cas d'échec, une `httpx.HTTPError` est levée.

```python
try:
    client.record_run(agent_id="uuid", status="completed")
except httpx.HTTPError as e:
    print(f"Échec d'envoi : {e}")
```

## Exemple complet

```python
import asyncio
from agent_obs import AgentObservabilityClient, monitor

client = AgentObservabilityClient(
    base_url="http://localhost:8000",
    api_key="ta-clé-api",
)
client.set_session("session-demo-001")

@monitor(agent_id="mon-agent")
async def chercher_reponse(question: str) -> str:
    await asyncio.sleep(0.5)
    return f"Réponse à : {question}"

async def main():
    result = await chercher_reponse("Qu'est-ce que LangGraph ?")
    print(result)
    client.close()

asyncio.run(main())
```
