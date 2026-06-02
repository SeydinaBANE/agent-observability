# TESTING.md — Guide des tests

## Stack de test

- **Framework** : pytest 8.x + pytest-asyncio
- **Base** : PostgreSQL réel (via Docker), pas de mock
- **Couverture** : pytest-cov (api/, core/, workers/)
- **Lint** : ruff + mypy
- **Isolation** : les tests utilisent `-p agent-observability-test` pour ne pas impacter la stack de production

## Lancer les tests

```bash
# Tous les tests avec couverture
./dev-cli.py test --coverage

# Rapide (stop au premier échec)
./dev-cli.py test --quick --failfast

# Un fichier spécifique
./dev-cli.py test -f tests/test_api.py

# Un test nommé
./dev-cli.py test -k "test_health"

# Sans le CLI (via make)
make test        # complet avec coverage
make test-quick  # rapide
```

Les tests démarrent automatiquement postgres + redis dans des conteneurs Docker avec le project name `agent-observability-test` (ne touche pas à la stack de production).

## Structure des tests

```
tests/
├── conftest.py          # Fixtures : engine, session, tenant, agent
├── test_api.py          # 8 tests : health, tenant, auth, agent, ingest, metrics, dashboard
├── test_detectors.py    # 2 tests : detect_loops, detect_hallucinations (sans LLM)
└── test_sdk.py          # 5 tests : client init, span, session, error, monitor decorator
```

### Fixtures principales (`conftest.py`)

| Fixture | Scope | Description |
|---|---|---|
| `engine` | session | Engine async pointant vers PostgreSQL test |
| `session` | function | Session SQLAlchemy (rollback automatique) |
| `test_tenant` | function | Tenant créé + cleanup |
| `test_agent` | function | Agent créé via API |

**Important** : les fixtures utilisent `app.dependency_overrides[get_db]` pour injecter la session de test dans FastAPI.

## Écrire un nouveau test

```python
async def test_mon_nouveau_endpoint(client_fixture, test_tenant):
    """Test nominal."""
    response = await client.get("/api/v1/...", headers={"X-API-Key": test_tenant["api_key"]})
    assert response.status_code == 200
    data = response.json()
    assert data["..."]

async def test_mon_endpoint_sans_auth(client_fixture):
    """Test cas d'erreur : pas d'auth."""
    response = await client.get("/api/v1/...")
    assert response.status_code == 401
```

## Tests sans dépendances externes

Les tests de détection ne requièrent **pas** de LLM :

- `test_detect_loops_no_session` : pattern matching (5 outputs identiques)
- `test_detect_hallucinations_no_input` : input vide → skip

Les tests SDK sont purement unitaires (pas de DB, pas d'API).

## Couverture

```bash
make test  # rapport en fin d'exécution
```

Cibles actuelles : **~62%** (workers Celery et dashboard non couverts — à améliorer).

## Bonnes pratiques

- Un test nominal + un cas d'erreur par fonction
- Nommer `test_<fonction>_<cas>`
- Pas de `print` dans les tests (utiliser `caplog`)
- Pas de `time.sleep` (préférer `await asyncio.sleep(0)`)
- Les tests API créent leurs propres données (pas de seed partagé)
- Nettoyage automatique via rollback de session
