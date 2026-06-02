import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import select

from core.config import settings
from core.database import async_session
from core.models import AgentRun, Anomaly


async def detect_loops(tenant_id: str, run_id: str, session_id: str | None, agent_id: str) -> None:
    if not session_id:
        return
    async with async_session() as db:
        result = await db.execute(
            select(AgentRun)
            .where(
                AgentRun.tenant_id == uuid.UUID(tenant_id),
                AgentRun.agent_id == uuid.UUID(agent_id),
                AgentRun.session_id == session_id,
                AgentRun.created_at >= datetime.now(UTC),
            )
            .order_by(AgentRun.created_at.desc())
            .limit(20)
        )
        recent_runs = result.scalars().all()
        if len(recent_runs) < 5:
            return
        consecutive_identical = 1
        for i in range(1, len(recent_runs)):
            if (
                recent_runs[i].output_preview == recent_runs[i - 1].output_preview
                and recent_runs[i].status == recent_runs[i - 1].status
            ):
                consecutive_identical += 1
            else:
                consecutive_identical = 1
            if consecutive_identical >= 5:
                anomaly = Anomaly(
                    run_id=uuid.UUID(run_id),
                    tenant_id=uuid.UUID(tenant_id),
                    anomaly_type="infinite_loop",
                    severity="critical",
                    title="Potentielle boucle infinie détectée",
                    description=f"L'agent a produit {consecutive_identical} sorties identiques consécutives dans la même session.",
                    evidence={
                        "session_id": session_id,
                        "consecutive_identical": consecutive_identical,
                        "recent_run_ids": [str(r.id) for r in recent_runs[:5]],
                    },
                )
                db.add(anomaly)
                await db.commit()
                break


async def detect_hallucinations(tenant_id: str, run_id: str, input_preview: str | None, output_preview: str | None) -> None:
    if not input_preview or not output_preview:
        return
    api_key = settings.openrouter_api_key or settings.openai_api_key
    if not api_key:
        return
    if settings.openrouter_api_key:
        base_url = settings.openrouter_base_url
        model = "openai/gpt-4o-mini"
    else:
        base_url = "https://api.openai.com/v1"
        model = "gpt-4o-mini"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://github.com/your-org/agent-observability",
                    "X-Title": "Agent Observability",
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "Tu es un détecteur d'hallucinations. Compare l'input et l'output d'un agent IA. "
                            'Réponds UNIQUEMENT par un JSON : {"is_hallucination": bool, "confidence": 0.0-1.0, "reason": "..."}. '
                            "Une hallucination = information dans l'output qui n'est pas supportée par l'input.",
                        },
                        {"role": "user", "content": f"Input: {input_preview}\n\nOutput: {output_preview}"},
                    ],
                    "temperature": 0.0,
                },
            )
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            import json

            verdict = json.loads(content)
            if verdict.get("is_hallucination") and verdict.get("confidence", 0) > 0.7:
                async with async_session() as db:
                    anomaly = Anomaly(
                        run_id=uuid.UUID(run_id),
                        tenant_id=uuid.UUID(tenant_id),
                        anomaly_type="hallucination",
                        severity="high" if verdict["confidence"] > 0.9 else "medium",
                        title="Hallucination potentielle détectée",
                        description=verdict.get("reason", ""),
                        evidence=verdict,
                    )
                    db.add(anomaly)
                    await db.commit()
    except Exception:
        pass
