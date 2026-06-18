import asyncio
from datetime import UTC

from celery import Task
from sqlalchemy import select

from core.database import async_session
from core.models import AgentRun
from workers.celery_app import celery_app
from workers.detectors import detect_hallucinations, detect_loops


class AsyncTask(Task):
    abstract = True

    def run(self, *args, **kwargs):
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio

            nest_asyncio.apply()
        return loop.run_until_complete(self._run(*args, **kwargs))

    async def _run(self, *args, **kwargs):
        raise NotImplementedError


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def analyze_run(self, run_id: str, tenant_id: str) -> dict:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_analyze_run_async(run_id, tenant_id))
    finally:
        loop.close()


async def _analyze_run_async(run_id: str, tenant_id: str) -> dict:
    async with async_session() as db:
        result = await db.execute(select(AgentRun).where(AgentRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            return {"status": "error", "message": "Run not found"}
        tasks = []
        tasks.append(detect_loops(tenant_id, run_id, run.session_id, str(run.agent_id)))
        tasks.append(detect_hallucinations(tenant_id, run_id, run.input_preview, run.output_preview))
        await asyncio.gather(*tasks)
    return {"status": "completed", "run_id": run_id}


@celery_app.task(max_retries=3, default_retry_delay=60)
def purge_old_traces() -> dict:
    from datetime import datetime, timedelta

    from sqlalchemy import create_engine, text

    from core.config import settings as s

    sync_engine = create_engine(s.database_url_sync, pool_pre_ping=True)
    cutoff = datetime.now(UTC) - timedelta(days=7)
    with sync_engine.connect() as conn:
        result = conn.execute(
            text("DELETE FROM agent_spans WHERE created_at < :cutoff"),
            {"cutoff": cutoff},
        )
        spans_deleted = result.rowcount
        result = conn.execute(
            text("DELETE FROM agent_runs WHERE created_at < :cutoff"),
            {"cutoff": cutoff},
        )
        runs_deleted = result.rowcount
        conn.commit()
    return {"spans_deleted": spans_deleted, "runs_deleted": runs_deleted}
