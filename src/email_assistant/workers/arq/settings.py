"""ARQ worker settings for durable email generation jobs."""

from __future__ import annotations

from typing import ClassVar

from arq.connections import RedisSettings

from email_assistant.config import get_settings
from email_assistant.domains.jobs.store import get_job_store
from email_assistant.workers.dispatch import close_arq_pool


async def startup(ctx: dict[str, object]) -> None:
    settings = get_settings()
    await get_job_store().setup()
    ctx["settings"] = settings


async def shutdown(ctx: dict[str, object]) -> None:
    await close_arq_pool()


_settings = get_settings()


class WorkerSettings:
    functions: ClassVar[list[object]] = []
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    max_jobs = _settings.job_worker_concurrency
    job_timeout = int(_settings.email_job_timeout_seconds)
    max_tries = _settings.job_max_attempts
    retry_jobs = True
