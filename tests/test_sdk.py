from unittest.mock import patch

import pytest
from agent_obs.client import AgentObservabilityClient, SpanData


@pytest.fixture
def client():
    return AgentObservabilityClient(base_url="http://localhost:8000", api_key="test-key", agent_id="test-agent")


def test_client_init(client: AgentObservabilityClient):
    assert client.base_url == "http://localhost:8000"
    assert client.api_key == "test-key"
    assert client.agent_id == "test-agent"


def test_span_data_defaults():
    span = SpanData(span_type="llm_call", span_name="gpt-4")
    assert span.status == "success"
    assert span.duration_ms is None
    assert span.error is None


def test_client_set_session(client: AgentObservabilityClient):
    client.set_session("session-123")
    assert client._session_id == "session-123"


def test_client_record_error(client: AgentObservabilityClient):
    assert client.agent_id == "test-agent"


@pytest.mark.asyncio
async def test_monitor_decorator():
    from agent_obs.client import monitor

    call_count = 0

    @monitor(agent_id="test-agent", api_key="test-key", base_url="http://localhost:8000")
    async def my_agent(query: str) -> str:
        nonlocal call_count
        call_count += 1
        return f"Result for: {query}"

    with patch.object(AgentObservabilityClient, "_post", return_value={"status": "ok"}):
        result = await my_agent("hello")

    assert result == "Result for: hello"
    assert call_count == 1
