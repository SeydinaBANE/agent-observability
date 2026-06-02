import time
import uuid
from typing import Any

from agent_obs.client import AgentObservabilityClient, SpanData


class ObservabilityCallback:
    def __init__(self, client: AgentObservabilityClient):
        self.client = client
        self._span_stack: list[tuple[str, float]] = []
        self._current_run_id: str | None = None
        self._total_tokens = 0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._total_cost = 0.0
        self._spans: list[SpanData] = []

    def on_chain_start(self, serialized: dict, inputs: dict, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", uuid.uuid4()))
        self._span_stack.append((run_id, time.monotonic()))

    def on_chain_end(self, outputs: dict, **kwargs: Any) -> None:
        if not self._span_stack:
            return
        _run_id, start = self._span_stack.pop()
        duration = int((time.monotonic() - start) * 1000)
        parent_id = self._span_stack[-1][0] if self._span_stack else None
        self._spans.append(
            SpanData(
                parent_span_id=parent_id,
                span_type="chain",
                span_name=str(kwargs.get("name", "chain")),
                output_data=outputs,
                duration_ms=duration,
                status="success",
            )
        )

    def on_llm_start(self, serialized: dict, prompts: list[str], **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", uuid.uuid4()))
        self._span_stack.append((run_id, time.monotonic()))

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        if not self._span_stack:
            return
        _run_id, start = self._span_stack.pop()
        duration = int((time.monotonic() - start) * 1000)
        parent_id = self._span_stack[-1][0] if self._span_stack else None
        try:
            llm_output = response.llm_output or {}
            token_usage = llm_output.get("token_usage", {})
            tokens = token_usage.get("total_tokens", 0)
            prompt_t = token_usage.get("prompt_tokens", 0)
            completion_t = token_usage.get("completion_tokens", 0)
            cost = (prompt_t * 0.00001) + (completion_t * 0.00003)
            self._total_tokens += tokens
            self._prompt_tokens += prompt_t
            self._completion_tokens += completion_t
            self._total_cost += cost
        except Exception:
            tokens = 0
            cost = 0.0
        self._spans.append(
            SpanData(
                parent_span_id=parent_id,
                span_type="llm_call",
                span_name=str(getattr(response, "model", "llm")),
                duration_ms=duration,
                tokens_used=tokens,
                cost_usd=cost,
                status="success",
            )
        )

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", uuid.uuid4()))
        self._span_stack.append((run_id, time.monotonic()))

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        if not self._span_stack:
            return
        _run_id, start = self._span_stack.pop()
        duration = int((time.monotonic() - start) * 1000)
        parent_id = self._span_stack[-1][0] if self._span_stack else None
        self._spans.append(
            SpanData(
                parent_span_id=parent_id,
                span_type="tool",
                span_name=str(kwargs.get("name", "tool")),
                output_data={"output": str(output)[:1000]},
                duration_ms=duration,
                status="success",
            )
        )

    def on_chain_error(self, error: Exception, **kwargs: Any) -> None:
        if not self._span_stack:
            return
        _run_id, start = self._span_stack.pop()
        duration = int((time.monotonic() - start) * 1000)
        parent_id = self._span_stack[-1][0] if self._span_stack else None
        self._spans.append(
            SpanData(
                parent_span_id=parent_id,
                span_type="chain",
                span_name=str(kwargs.get("name", "chain")),
                error=str(error),
                duration_ms=duration,
                status="error",
            )
        )

    def flush(self, input_preview: str | None = None, output_preview: str | None = None) -> dict | None:
        if not self._spans:
            return None
        result = self.client.record_run(
            input_preview=input_preview,
            output_preview=output_preview,
            total_tokens=self._total_tokens,
            prompt_tokens=self._prompt_tokens,
            completion_tokens=self._completion_tokens,
            cost_usd=self._total_cost,
            spans=self._spans,
        )
        self._spans.clear()
        self._total_tokens = 0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._total_cost = 0.0
        return result
