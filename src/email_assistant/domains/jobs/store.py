"""Durable job persistence for background draft work."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, Protocol

import orjson
from email_assistant.config import get_settings
from email_assistant.db.pool import get_pool, is_sqlite_mode
from email_assistant.domains.jobs.schemas import JobRecord, JobStatus, JobType, utc_now


class JobStore(Protocol):
    async def setup(self) -> None: ...

    async def create_job(
        self,
        *,
        job_type: JobType,
        case_id: str,
        payload: dict[str, Any],
        max_attempts: int,
    ) -> JobRecord: ...

    async def get(self, job_id: str) -> JobRecord | None: ...

    async def mark_running(self, job_id: str) -> JobRecord | None: ...

    async def mark_succeeded(self, job_id: str) -> JobRecord | None: ...

    async def mark_failed(self, job_id: str, *, error: str) -> JobRecord | None: ...

    async def mark_timed_out(self, job_id: str, *, error: str = "") -> JobRecord | None: ...

    async def mark_retry(self, job_id: str, *, error: str) -> JobRecord | None: ...

    async def clear(self) -> None: ...


_JOBS_TABLE = "background_jobs"

_SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS {_JOBS_TABLE} (
    job_id         text PRIMARY KEY,
    job_type       text NOT NULL,
    status         text NOT NULL DEFAULT 'queued',
    case_id        text NOT NULL,
    payload        jsonb NOT NULL,
    attempts       integer NOT NULL DEFAULT 0,
    max_attempts   integer NOT NULL DEFAULT 3,
    error          text NOT NULL DEFAULT '',
    created_at     timestamptz NOT NULL,
    updated_at     timestamptz NOT NULL,
    started_at     timestamptz,
    finished_at    timestamptz
);

CREATE INDEX IF NOT EXISTS idx_background_jobs_case_id
    ON {_JOBS_TABLE}(case_id);

CREATE INDEX IF NOT EXISTS idx_background_jobs_status
    ON {_JOBS_TABLE}(status);
"""


def _parse_tz(value: object) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    raise ValueError(f"Expected datetime, got {type(value)}")


def _parse_optional_tz(value: object) -> datetime | None:
    if value is None:
        return None
    return _parse_tz(value)


def _row_to_job(row: Any) -> JobRecord:
    payload_raw = row["payload"]
    if isinstance(payload_raw, str | bytes | bytearray):
        payload = orjson.loads(payload_raw)
    elif isinstance(payload_raw, dict):
        payload = payload_raw
    else:
        payload = {}
    return JobRecord(
        job_id=row["job_id"],
        job_type=JobType(row["job_type"]),
        status=JobStatus(row["status"]),
        case_id=row["case_id"],
        payload=payload,
        attempts=int(row["attempts"]),
        max_attempts=int(row["max_attempts"]),
        error=row["error"] or "",
        created_at=_parse_tz(row["created_at"]),
        updated_at=_parse_tz(row["updated_at"]),
        started_at=_parse_optional_tz(row["started_at"]),
        finished_at=_parse_optional_tz(row["finished_at"]),
    )


class InMemoryJobStore:
    """Process-local job store for tests and local development without Postgres."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}

    async def setup(self) -> None:
        return None

    async def create_job(
        self,
        *,
        job_type: JobType,
        case_id: str,
        payload: dict[str, Any],
        max_attempts: int,
    ) -> JobRecord:
        now = utc_now()
        job = JobRecord(
            job_id=str(uuid.uuid4()),
            job_type=job_type,
            status=JobStatus.QUEUED,
            case_id=case_id.upper(),
            payload=payload,
            attempts=0,
            max_attempts=max_attempts,
            created_at=now,
            updated_at=now,
        )
        self._jobs[job.job_id] = job
        return job

    async def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    async def mark_running(self, job_id: str) -> JobRecord | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        now = utc_now()
        updated = replace(
            job,
            status=JobStatus.RUNNING,
            attempts=job.attempts + 1,
            updated_at=now,
            started_at=job.started_at or now,
            error="",
        )
        self._jobs[job_id] = updated
        return updated

    async def mark_succeeded(self, job_id: str) -> JobRecord | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        now = utc_now()
        updated = replace(
            job,
            status=JobStatus.SUCCEEDED,
            updated_at=now,
            finished_at=now,
            error="",
        )
        self._jobs[job_id] = updated
        return updated

    async def mark_failed(self, job_id: str, *, error: str) -> JobRecord | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        now = utc_now()
        updated = replace(
            job,
            status=JobStatus.FAILED,
            updated_at=now,
            finished_at=now,
            error=error,
        )
        self._jobs[job_id] = updated
        return updated

    async def mark_timed_out(self, job_id: str, *, error: str = "") -> JobRecord | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        now = utc_now()
        updated = replace(
            job,
            status=JobStatus.TIMED_OUT,
            updated_at=now,
            finished_at=now,
            error=error or "Job timed out",
        )
        self._jobs[job_id] = updated
        return updated

    async def mark_retry(self, job_id: str, *, error: str) -> JobRecord | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        now = utc_now()
        updated = replace(
            job,
            status=JobStatus.QUEUED,
            updated_at=now,
            error=error,
        )
        self._jobs[job_id] = updated
        return updated

    async def clear(self) -> None:
        self._jobs.clear()


class PostgresJobStore:
    """PostgreSQL-backed durable job store for production."""

    def __init__(self, *, database_url: str) -> None:
        self._database_url = database_url

    async def setup(self) -> None:
        connection = await self._connect()
        try:
            await connection.execute(_SCHEMA_SQL)
        finally:
            await self._release(connection)

    async def create_job(
        self,
        *,
        job_type: JobType,
        case_id: str,
        payload: dict[str, Any],
        max_attempts: int,
    ) -> JobRecord:
        now = utc_now()
        job_id = str(uuid.uuid4())
        payload_json = orjson.dumps(payload).decode()
        connection = await self._connect()
        try:
            await connection.execute(
                f"""
                INSERT INTO {_JOBS_TABLE}
                    (job_id, job_type, status, case_id, payload, attempts, max_attempts,
                     error, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5::jsonb, 0, $6, '', $7, $7)
                """,
                job_id,
                job_type,
                JobStatus.QUEUED,
                case_id.upper(),
                payload_json,
                max_attempts,
                now,
            )
        finally:
            await self._release(connection)
        return await self._require(job_id)

    async def get(self, job_id: str) -> JobRecord | None:
        connection = await self._connect()
        try:
            row = await connection.fetchrow(
                f"SELECT * FROM {_JOBS_TABLE} WHERE job_id = $1",
                job_id,
            )
        finally:
            await self._release(connection)
        if row is None:
            return None
        return _row_to_job(row)

    async def mark_running(self, job_id: str) -> JobRecord | None:
        now = utc_now()
        connection = await self._connect()
        try:
            row = await connection.fetchrow(
                f"""
                UPDATE {_JOBS_TABLE}
                SET status = $2,
                    attempts = attempts + 1,
                    updated_at = $3,
                    started_at = COALESCE(started_at, $3),
                    error = ''
                WHERE job_id = $1
                RETURNING *
                """,
                job_id,
                JobStatus.RUNNING,
                now,
            )
        finally:
            await self._release(connection)
        if row is None:
            return None
        return _row_to_job(row)

    async def mark_succeeded(self, job_id: str) -> JobRecord | None:
        return await self._mark_terminal(job_id, status=JobStatus.SUCCEEDED, error="")

    async def mark_failed(self, job_id: str, *, error: str) -> JobRecord | None:
        return await self._mark_terminal(job_id, status=JobStatus.FAILED, error=error)

    async def mark_timed_out(self, job_id: str, *, error: str = "") -> JobRecord | None:
        return await self._mark_terminal(
            job_id,
            status=JobStatus.TIMED_OUT,
            error=error or "Job timed out",
        )

    async def mark_retry(self, job_id: str, *, error: str) -> JobRecord | None:
        now = utc_now()
        connection = await self._connect()
        try:
            row = await connection.fetchrow(
                f"""
                UPDATE {_JOBS_TABLE}
                SET status = $2, updated_at = $3, error = $4
                WHERE job_id = $1
                RETURNING *
                """,
                job_id,
                JobStatus.QUEUED,
                now,
                error,
            )
        finally:
            await self._release(connection)
        if row is None:
            return None
        return _row_to_job(row)

    async def clear(self) -> None:
        connection = await self._connect()
        try:
            await connection.execute(f"DELETE FROM {_JOBS_TABLE}")
        finally:
            await self._release(connection)

    async def _mark_terminal(
        self,
        job_id: str,
        *,
        status: JobStatus,
        error: str,
    ) -> JobRecord | None:
        now = utc_now()
        connection = await self._connect()
        try:
            row = await connection.fetchrow(
                f"""
                UPDATE {_JOBS_TABLE}
                SET status = $2, updated_at = $3, finished_at = $3, error = $4
                WHERE job_id = $1
                RETURNING *
                """,
                job_id,
                status,
                now,
                error,
            )
        finally:
            await self._release(connection)
        if row is None:
            return None
        return _row_to_job(row)

    async def _require(self, job_id: str) -> JobRecord:
        job = await self.get(job_id)
        if job is None:
            raise RuntimeError(f"Job {job_id} was not found after insert")
        return job

    async def _connect(self) -> Any:
        pool = get_pool()
        return await pool.acquire()

    async def _release(self, connection: Any) -> None:
        pool = get_pool()
        await pool.release(connection)


@lru_cache(maxsize=1)
def get_job_store() -> JobStore:
    settings = get_settings()
    if is_sqlite_mode() or settings.job_store_backend != "postgres":
        return InMemoryJobStore()
    return PostgresJobStore(database_url=settings.database_url)
