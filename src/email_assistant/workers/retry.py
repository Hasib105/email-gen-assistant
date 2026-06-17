"""Shared retry classification for background jobs."""

from __future__ import annotations

import httpx

TRANSIENT_JOB_EXCEPTIONS: tuple[type[BaseException], ...] = (
    TimeoutError,
    ConnectionError,
    OSError,
    httpx.HTTPError,
)


def is_transient_job_error(exc: BaseException) -> bool:
    if isinstance(exc, TRANSIENT_JOB_EXCEPTIONS):
        return True
    cause = exc.__cause__
    return isinstance(cause, TRANSIENT_JOB_EXCEPTIONS)
