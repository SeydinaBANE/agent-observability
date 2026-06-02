from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "development"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/agent_obs"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/agent_obs"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    langsmith_api_key: str = ""
    langsmith_project: str = "agent-observability"

    openai_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    ollama_base_url: str = "http://localhost:11434"
    llm_judge_model: str = "gpt-4o-mini"

    retention_days_raw: int = 7
    retention_days_aggregated: int = 90

    rate_limit_per_second: int = 100
    max_traces_per_run: int = 10000

    s3_endpoint: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "agent-obs-backups"

    sentry_dsn: str = ""

    demo_api_key: str = "demo-key-local-dev"

    model_config = {"env_prefix": "AGENT_OBS_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
