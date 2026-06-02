import functools
import os
import time
from dataclasses import dataclass, field

import httpx


@dataclass
class SpanData:
    parent_span_id: str | None = None
    span_type: str = "llm_call"
    span_name: str = ""
    input_data: dict | None = None
    output_data: dict | None = None
    duration_ms: int | None = None
    tokens_used: int | None = None
    cost_usd: float | None = None
    status: str = "success"
    error: str | None = None


@dataclass
class RunData:
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
    spans: list[SpanData] = field(default_factory=list)


class AgentObservabilityClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        agent_id: str | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        batch_size: int = 10,
    ):
        self.base_url = base_url or os.getenv("AGENT_OBS_URL", "http://localhost:8000") or "http://localhost:8000"
        self.api_key = api_key or os.getenv("AGENT_OBS_API_KEY", "")
        self.agent_id = agent_id or os.getenv("AGENT_OBS_AGENT_ID", "")
        self.timeout = timeout
        self.max_retries = max_retries
        self.batch_size = batch_size
        self._pending_runs: list[RunData] = []
        self._session_id: str | None = None
        self._http = httpx.Client(base_url=self.base_url, timeout=timeout)

    def set_session(self, session_id: str) -> None:
        self._session_id = session_id

    def _headers(self) -> dict:
        return {"X-API-Key": self.api_key, "Content-Type": "application/json"}

    def _post(self, path: str, payload: dict) -> dict:
        for attempt in range(self.max_retries):
            try:
                resp = self._http.post(path, json=payload, headers=self._headers())
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2**attempt)
        return {}

    def record_run(
        self,
        agent_id: str | None = None,
        input_preview: str | None = None,
        output_preview: str | None = None,
        duration_ms: int | None = None,
        total_tokens: int | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        cost_usd: float | None = None,
        status: str = "completed",
        error: str | None = None,
        metadata: dict | None = None,
        spans: list[SpanData] | None = None,
    ) -> dict | None:
        payload = {
            "agent_id": agent_id or self.agent_id,
            "session_id": self._session_id,
            "input_preview": input_preview,
            "output_preview": output_preview,
            "duration_ms": duration_ms,
            "total_tokens": total_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": cost_usd,
            "status": status,
            "error": error,
            "metadata": metadata,
            "spans": [s.__dict__ for s in spans] if spans else None,
        }
        return self._post("/api/v1/ingest", payload)

    def record_error(self, agent_id: str | None = None, error: str = "", metadata: dict | None = None) -> dict | None:
        return self.record_run(agent_id=agent_id, status="error", error=error, metadata=metadata)

    def close(self) -> None:
        self._http.close()


def monitor(
    agent_id: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
):
    def decorator(func):
        client = AgentObservabilityClient(base_url=base_url, api_key=api_key, agent_id=agent_id)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                result = await func(*args, **kwargs)
                duration = int((time.monotonic() - start) * 1000)
                client.record_run(
                    duration_ms=duration, status="completed", input_preview=str(kwargs), output_preview=str(result)[:500]
                )
                return result
            except Exception as e:
                duration = int((time.monotonic() - start) * 1000)
                client.record_run(duration_ms=duration, status="error", error=str(e))
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                result = func(*args, **kwargs)
                duration = int((time.monotonic() - start) * 1000)
                client.record_run(
                    duration_ms=duration, status="completed", input_preview=str(kwargs), output_preview=str(result)[:500]
                )
                return result
            except Exception as e:
                duration = int((time.monotonic() - start) * 1000)
                client.record_run(duration_ms=duration, status="error", error=str(e))
                raise

        if __import__("inspect").iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
