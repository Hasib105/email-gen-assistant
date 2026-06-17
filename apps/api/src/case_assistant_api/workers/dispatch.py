"""Job dispatch for API handlers."""

from __future__ import annotations

import structlog
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from fastapi import BackgroundTasks

from case_assistant_api.config import Settings, get_settings
from case_assistant_api.domains.jobs.schemas import JobType
from case_assistant_api.domains.jobs.store import get_job_store

logger = structlog.get_logger()

_arq_pool: ArqRedis | None = None


async def get_arq_pool() -> ArqRedis:
    global _arq_pool  # noqa: PLW0603
    if _arq_pool is None:
        settings = get_settings()
        _arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _arq_pool


async def close_arq_pool() -> None:
    global _arq_pool  # noqa: PLW0603
    if _arq_pool is not None:
        await _arq_pool.close()
        _arq_pool = None


class EmailJobDispatcher:
    """Create durable jobs and dispatch them to the configured executor."""

    def __init__(
        self,
        *,
        background_tasks: BackgroundTasks | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._background_tasks = background_tasks
        self._settings = settings or get_settings()

    async def dispatch_generate_email(
        self,
        *,
        case_id: str,
        user_id: str = "",
    ) -> str:
        payload = {"case_id": case_id, "user_id": user_id}
        return await self._dispatch(
            job_type=JobType.GENERATE_DRAFT,
            case_id=case_id,
            payload=payload,
        )

    async def _dispatch(
        self,
        *,
        job_type: JobType,
        case_id: str,
        payload: dict[str, str],
    ) -> str:
        store = get_job_store()
        job = await store.create_job(
            job_type=job_type,
            case_id=case_id,
            payload=payload,
            max_attempts=self._settings.job_max_attempts,
        )
        logger.info(
            "email_job_enqueued",
            job_id=job.job_id,
            job_type=job_type,
            case_id=case_id,
            executor=self._settings.job_executor_backend,
        )

        if self._settings.job_executor_backend == "arq":
            await self._enqueue_arq(job.job_id)
        else:
            if self._background_tasks is None:
                raise RuntimeError(
                    "BackgroundTasks is required when job_executor_backend=background"
                )

        return job.job_id

    async def _enqueue_arq(self, job_id: str) -> None:
        pool = await get_arq_pool()
        await pool.enqueue_job("run_email_job", job_id)
