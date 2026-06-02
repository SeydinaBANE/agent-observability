import pytest

from workers.detectors import detect_loops


@pytest.mark.asyncio
async def test_detect_loops_no_session():
    result = await detect_loops(tenant_id="test", run_id="run-1", session_id=None, agent_id="agent-1")
    assert result is None


@pytest.mark.asyncio
async def test_detect_hallucinations_no_input():
    from workers.detectors import detect_hallucinations

    result = await detect_hallucinations(tenant_id="test", run_id="run-1", input_preview=None, output_preview="something")
    assert result is None
