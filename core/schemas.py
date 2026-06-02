from pydantic import BaseModel, Field


class HealthCheck(BaseModel):
    status: str
    version: str
    timestamp: str


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")
    api_key: str = Field(min_length=16, max_length=128)


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    is_active: bool
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    tenant_id: str


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    version: str = Field(min_length=1, max_length=50)
    langgraph_version: str = ""


class AgentResponse(BaseModel):
    id: str
    name: str
    version: str
    langgraph_version: str
    is_active: bool
    created_at: str


class SpanPayload(BaseModel):
    parent_span_id: str | None = None
    span_type: str = Field(max_length=50)
    span_name: str = Field(max_length=255)
    input_data: dict | None = None
    output_data: dict | None = None
    duration_ms: int | None = None
    tokens_used: int | None = None
    cost_usd: float | None = None
    status: str = "success"
    error: str | None = None


class IngestRunRequest(BaseModel):
    agent_id: str
    session_id: str | None = None
    input_preview: str | None = None
    output_preview: str | None = None
    duration_ms: int | None = None
    total_tokens: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None
    status: str = "completed"
    error: str | None = None
    metadata: dict | None = None
    spans: list[SpanPayload] | None = None


class IngestRunResponse(BaseModel):
    run_id: str
    status: str


class MetricsResponse(BaseModel):
    total_runs: int
    avg_duration_ms: float
    total_tokens: int
    total_cost_usd: float
    error_count: int
    success_count: int
    period_hours: str


class TraceQuery(BaseModel):
    id: str
    session_id: str | None
    input_preview: str | None
    output_preview: str | None
    duration_ms: int | None
    total_tokens: int | None
    cost_usd: float | None
    status: str
    error: str | None
    created_at: str


class AnomalyResponse(BaseModel):
    id: str
    run_id: str
    anomaly_type: str
    severity: str
    title: str
    description: str | None
    evidence: dict | None
    is_resolved: bool
    created_at: str


class AlertsResponse(BaseModel):
    id: str
    rule_name: str
    metric: str
    threshold: float
    current_value: float
    status: str
    created_at: str


class DashboardStats(BaseModel):
    total_runs: int
    total_tokens: int
    total_cost_usd: float
    avg_duration_ms: float
    errors: int
    active_anomalies: int
    active_agents: int


class CostReport(BaseModel):
    agent_name: str
    agent_id: str
    runs: int
    total_cost_usd: float
    total_tokens: int
    avg_duration_ms: float
