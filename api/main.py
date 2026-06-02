import uuid
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import create_access_token, get_authenticated_tenant, get_tenant_from_api_key
from core.database import Base, engine, get_db
from core.models import Agent, AgentRun, AgentSpan, Alert, Anomaly, Tenant
from core.schemas import (
    AgentCreate,
    AgentResponse,
    AlertsResponse,
    AnomalyResponse,
    CostReport,
    DashboardStats,
    HealthCheck,
    IngestRunRequest,
    IngestRunResponse,
    MetricsResponse,
    TenantCreate,
    TenantResponse,
    TokenResponse,
    TraceQuery,
)

app = FastAPI(
    title="Agent Observability API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    from api.auth import hash_api_key
    from core.config import settings

    demo_key = settings.demo_api_key
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO tenants (id, name, slug, api_key_hash, plan, is_active, created_at) "
                "VALUES (:id, :name, :slug, :hash, :plan, :active, :now) "
                "ON CONFLICT (name) DO NOTHING"
            ),
            {
                "id": uuid.uuid4(),
                "name": "demo",
                "slug": "demo",
                "hash": hash_api_key(demo_key),
                "plan": "free",
                "active": True,
                "now": datetime.now(UTC),
            },
        )


@app.get("/health", response_model=HealthCheck)
async def health():
    return HealthCheck(status="ok", version="0.1.0", timestamp=datetime.now(UTC).isoformat())


@app.post("/api/v1/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(payload: TenantCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Tenant).where(Tenant.slug == payload.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tenant already exists")
    from api.auth import hash_api_key

    tenant = Tenant(name=payload.name, slug=payload.slug, api_key_hash=hash_api_key(payload.api_key))
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return TenantResponse(
        id=str(tenant.id),
        name=tenant.name,
        slug=tenant.slug,
        plan=tenant.plan,
        is_active=tenant.is_active,
        created_at=tenant.created_at.isoformat(),
    )


@app.post("/api/v1/auth/token", response_model=TokenResponse)
async def get_token(db: AsyncSession = Depends(get_db), tenant: Tenant = Depends(get_tenant_from_api_key)):
    token = create_access_token(str(tenant.id))
    return TokenResponse(access_token=token, token_type="bearer", tenant_id=str(tenant.id))


@app.get("/api/v1/agents", response_model=list[AgentResponse])
async def list_agents(db: AsyncSession = Depends(get_db), tenant: Tenant = Depends(get_authenticated_tenant)):
    result = await db.execute(select(Agent).where(Agent.tenant_id == tenant.id))
    agents = result.scalars().all()
    return [
        AgentResponse(
            id=str(a.id),
            name=a.name,
            version=a.version,
            langgraph_version=a.langgraph_version,
            is_active=a.is_active,
            created_at=a.created_at.isoformat(),
        )
        for a in agents
    ]


@app.post("/api/v1/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def register_agent(
    payload: AgentCreate, db: AsyncSession = Depends(get_db), tenant: Tenant = Depends(get_authenticated_tenant)
):
    existing = await db.execute(select(Agent).where(Agent.tenant_id == tenant.id, Agent.name == payload.name))
    if existing.scalar_one_or_none():
        existing_agent = existing.scalar_one()
        existing_agent.version = payload.version
        existing_agent.langgraph_version = payload.langgraph_version
        await db.commit()
        await db.refresh(existing_agent)
        return AgentResponse(
            id=str(existing_agent.id),
            name=existing_agent.name,
            version=existing_agent.version,
            langgraph_version=existing_agent.langgraph_version,
            is_active=existing_agent.is_active,
            created_at=existing_agent.created_at.isoformat(),
        )
    agent = Agent(tenant_id=tenant.id, name=payload.name, version=payload.version, langgraph_version=payload.langgraph_version)
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return AgentResponse(
        id=str(agent.id),
        name=agent.name,
        version=agent.version,
        langgraph_version=agent.langgraph_version,
        is_active=agent.is_active,
        created_at=agent.created_at.isoformat(),
    )


@app.post("/api/v1/ingest", response_model=IngestRunResponse, status_code=status.HTTP_201_CREATED)
async def ingest_run(
    payload: IngestRunRequest, db: AsyncSession = Depends(get_db), tenant: Tenant = Depends(get_tenant_from_api_key)
):
    result = await db.execute(select(Agent).where(Agent.tenant_id == tenant.id, Agent.id == uuid.UUID(payload.agent_id)))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    run = AgentRun(
        agent_id=agent.id,
        tenant_id=tenant.id,
        session_id=payload.session_id,
        input_preview=payload.input_preview,
        output_preview=payload.output_preview,
        duration_ms=payload.duration_ms,
        total_tokens=payload.total_tokens,
        prompt_tokens=payload.prompt_tokens,
        completion_tokens=payload.completion_tokens,
        cost_usd=payload.cost_usd,
        status=payload.status,
        error=payload.error,
        run_metadata=payload.metadata,
    )
    db.add(run)
    await db.flush()
    if payload.spans:
        for span_data in payload.spans:
            span = AgentSpan(
                run_id=run.id,
                tenant_id=tenant.id,
                parent_span_id=uuid.UUID(span_data.parent_span_id) if span_data.parent_span_id else None,
                span_type=span_data.span_type,
                span_name=span_data.span_name,
                input_data=span_data.input_data,
                output_data=span_data.output_data,
                duration_ms=span_data.duration_ms,
                tokens_used=span_data.tokens_used,
                cost_usd=span_data.cost_usd,
                status=span_data.status,
                error=span_data.error,
            )
            db.add(span)
    await db.commit()
    await db.refresh(run)
    return IngestRunResponse(run_id=str(run.id), status=run.status)


@app.get("/api/v1/metrics/{agent_id}", response_model=MetricsResponse)
async def get_metrics(
    agent_id: str,
    since: str = Query(default="24h"),
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_authenticated_tenant),
):
    hours_map = {"1h": 1, "6h": 6, "24h": 24, "7d": 168, "30d": 720}
    hours = hours_map.get(since, 24)
    query = text("""
        SELECT
            COUNT(*) as total_runs,
            COALESCE(AVG(duration_ms), 0) as avg_duration_ms,
            COALESCE(SUM(total_tokens), 0) as total_tokens,
            COALESCE(SUM(cost_usd), 0) as total_cost_usd,
            COALESCE(SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END), 0) as error_count,
            COALESCE(SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END), 0) as success_count
        FROM agent_runs
        WHERE agent_id = :agent_id
          AND tenant_id = :tenant_id
          AND created_at >= NOW() - make_interval(hours => :hours)
    """)
    result = await db.execute(query, {"agent_id": agent_id, "tenant_id": str(tenant.id), "hours": hours})
    row = result.mappings().fetchone()
    if not row:
        return MetricsResponse(
            total_runs=0,
            avg_duration_ms=0.0,
            total_tokens=0,
            total_cost_usd=0.0,
            error_count=0,
            success_count=0,
            period_hours=since,
        )
    return MetricsResponse(
        total_runs=row["total_runs"] or 0,
        avg_duration_ms=round(row["avg_duration_ms"] or 0, 2),
        total_tokens=row["total_tokens"] or 0,
        total_cost_usd=round(row["total_cost_usd"] or 0, 6),
        error_count=row["error_count"] or 0,
        success_count=row["success_count"] or 0,
        period_hours=since,
    )


@app.get("/api/v1/traces/{agent_id}", response_model=list[TraceQuery])
async def get_traces(
    agent_id: str,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_authenticated_tenant),
):
    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.agent_id == uuid.UUID(agent_id), AgentRun.tenant_id == tenant.id)
        .order_by(AgentRun.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    runs = result.scalars().all()
    return [
        TraceQuery(
            id=str(r.id),
            session_id=r.session_id,
            input_preview=r.input_preview,
            output_preview=r.output_preview,
            duration_ms=r.duration_ms,
            total_tokens=r.total_tokens,
            cost_usd=r.cost_usd,
            status=r.status,
            error=r.error,
            created_at=r.created_at.isoformat(),
        )
        for r in runs
    ]


@app.get("/api/v1/anomalies/{agent_id}", response_model=list[AnomalyResponse])
async def get_anomalies(
    agent_id: str,
    limit: int = Query(default=50, le=500),
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_authenticated_tenant),
):
    result = await db.execute(
        select(Anomaly)
        .join(AgentRun, Anomaly.run_id == AgentRun.id)
        .where(AgentRun.agent_id == uuid.UUID(agent_id), AgentRun.tenant_id == tenant.id, Anomaly.is_resolved.is_(False))
        .order_by(Anomaly.created_at.desc())
        .limit(limit)
    )
    anomalies = result.scalars().all()
    return [
        AnomalyResponse(
            id=str(a.id),
            run_id=str(a.run_id),
            anomaly_type=a.anomaly_type,
            severity=a.severity,
            title=a.title,
            description=a.description,
            evidence=a.evidence,
            is_resolved=a.is_resolved,
            created_at=a.created_at.isoformat(),
        )
        for a in anomalies
    ]


@app.get("/api/v1/alerts", response_model=list[AlertsResponse])
async def get_alerts(
    limit: int = Query(default=50, le=500),
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_authenticated_tenant),
):
    result = await db.execute(
        select(Alert).where(Alert.tenant_id == tenant.id, Alert.status == "firing").order_by(Alert.created_at.desc()).limit(limit)
    )
    alerts = result.scalars().all()
    return [
        AlertsResponse(
            id=str(a.id),
            rule_name=a.rule_name,
            metric=a.metric,
            threshold=a.threshold,
            current_value=a.current_value,
            status=a.status,
            created_at=a.created_at.isoformat(),
        )
        for a in alerts
    ]


@app.get("/api/v1/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    since: str = Query(default="24h"),
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_authenticated_tenant),
):
    hours_map = {"1h": 1, "6h": 6, "24h": 24, "7d": 168, "30d": 720}
    hours = hours_map.get(since, 24)
    query = text("""
        SELECT
            COALESCE(COUNT(DISTINCT ar.id), 0) as total_runs,
            COALESCE(SUM(ar.total_tokens), 0) as total_tokens,
            COALESCE(SUM(ar.cost_usd), 0) as total_cost_usd,
            COALESCE(AVG(ar.duration_ms), 0) as avg_duration_ms,
            COALESCE(SUM(CASE WHEN ar.status = 'error' THEN 1 ELSE 0 END), 0) as errors,
            COALESCE(SUM(CASE WHEN an.id IS NOT NULL AND an.is_resolved = FALSE THEN 1 ELSE 0 END), 0) as active_anomalies,
            COALESCE(COUNT(DISTINCT ar.agent_id), 0) as active_agents
        FROM agent_runs ar
        LEFT JOIN anomalies an ON an.run_id = ar.id
        WHERE ar.tenant_id = :tenant_id
          AND ar.created_at >= NOW() - make_interval(hours => :hours)
    """)
    result = await db.execute(query, {"tenant_id": str(tenant.id), "hours": hours})
    row = result.mappings().fetchone()
    if not row:
        return DashboardStats(
            total_runs=0, total_tokens=0, total_cost_usd=0.0, avg_duration_ms=0.0, errors=0, active_anomalies=0, active_agents=0
        )
    return DashboardStats(
        total_runs=row["total_runs"] or 0,
        total_tokens=row["total_tokens"] or 0,
        total_cost_usd=round(row["total_cost_usd"] or 0, 2),
        avg_duration_ms=round(row["avg_duration_ms"] or 0, 2),
        errors=row["errors"] or 0,
        active_anomalies=row["active_anomalies"] or 0,
        active_agents=row["active_agents"] or 0,
    )


@app.get("/api/v1/costs", response_model=list[CostReport])
async def get_cost_report(
    since: str = Query(default="30d"),
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_authenticated_tenant),
):
    hours_map = {"7d": 168, "30d": 720, "90d": 2160}
    hours = hours_map.get(since, 720)
    query = text("""
        SELECT
            a.name as agent_name,
            a.id as agent_id,
            COUNT(ar.id) as runs,
            COALESCE(SUM(ar.cost_usd), 0) as total_cost,
            COALESCE(SUM(ar.total_tokens), 0) as total_tokens,
            COALESCE(AVG(ar.duration_ms), 0) as avg_duration
        FROM agents a
        LEFT JOIN agent_runs ar ON ar.agent_id = a.id AND ar.created_at >= NOW() - make_interval(hours => :hours)
        WHERE a.tenant_id = :tenant_id
        GROUP BY a.id, a.name
        ORDER BY total_cost DESC
    """)
    result = await db.execute(query, {"tenant_id": str(tenant.id), "hours": hours})
    rows = result.mappings().fetchall()
    return [
        CostReport(
            agent_name=row["agent_name"],
            agent_id=str(row["agent_id"]),
            runs=row["runs"] or 0,
            total_cost_usd=round(row["total_cost"] or 0, 4),
            total_tokens=row["total_tokens"] or 0,
            avg_duration_ms=round(row["avg_duration"] or 0, 2),
        )
        for row in rows
    ]
