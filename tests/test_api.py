import pytest
from httpx import AsyncClient

from core.models import Tenant


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_create_tenant(client: AsyncClient):
    resp = await client.post(
        "/api/v1/tenants",
        json={"name": "New Client", "slug": "new-client", "api_key": "my-api-key-1234567890123456"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "New Client"
    assert data["slug"] == "new-client"


@pytest.mark.asyncio
async def test_create_tenant_duplicate(client: AsyncClient, test_tenant: Tenant):
    resp = await client.post(
        "/api/v1/tenants",
        json={"name": test_tenant.name, "slug": test_tenant.slug, "api_key": "another-key-1234567890123456"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_auth_token(client: AsyncClient, test_tenant: Tenant):
    resp = await client.post(
        "/api/v1/auth/token",
        headers={"X-API-Key": "test-key-12345678"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_agent(client: AsyncClient, test_tenant: Tenant):
    resp = await client.post(
        "/api/v1/agents",
        json={"name": "research-agent", "version": "1.0.0", "langgraph_version": "0.2.60"},
        headers={"X-API-Key": "test-key-12345678"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "research-agent"
    assert data["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_ingest_run(client: AsyncClient, test_tenant: Tenant):
    agent_resp = await client.post(
        "/api/v1/agents",
        json={"name": "test-agent", "version": "1.0.0"},
        headers={"X-API-Key": "test-key-12345678"},
    )
    agent_id = agent_resp.json()["id"]
    resp = await client.post(
        "/api/v1/ingest",
        json={
            "agent_id": agent_id,
            "input_preview": "What is the capital of France?",
            "output_preview": "Paris is the capital of France.",
            "duration_ms": 1500,
            "total_tokens": 150,
            "cost_usd": 0.003,
            "status": "completed",
        },
        headers={"X-API-Key": "test-key-12345678"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "run_id" in data
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_get_metrics(client: AsyncClient, test_tenant: Tenant):
    agent_resp = await client.post(
        "/api/v1/agents",
        json={"name": "metrics-agent", "version": "1.0.0"},
        headers={"X-API-Key": "test-key-12345678"},
    )
    agent_id = agent_resp.json()["id"]
    await client.post(
        "/api/v1/ingest",
        json={"agent_id": agent_id, "duration_ms": 100, "total_tokens": 50, "cost_usd": 0.001, "status": "completed"},
        headers={"X-API-Key": "test-key-12345678"},
    )
    resp = await client.get(f"/api/v1/metrics/{agent_id}?since=7d", headers={"X-API-Key": "test-key-12345678"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_runs"] >= 1


@pytest.mark.asyncio
async def test_dashboard_stats(client: AsyncClient, test_tenant: Tenant):
    resp = await client.get("/api/v1/dashboard?since=24h", headers={"X-API-Key": "test-key-12345678"})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_runs" in data
    assert "total_cost_usd" in data
