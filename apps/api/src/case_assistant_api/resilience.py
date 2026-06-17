"""Small retry helpers for transient integration failures."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


async def retry_async[T](
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int,
    initial_delay_seconds: float = 0.2,
    retry_exceptions: tuple[type[BaseException], ...] = (Exception,),
    on_retry: Callable[[int, BaseException], None] | None = None,
) -> T:
    """Run an async operation with bounded exponential backoff."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    delay = initial_delay_seconds
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except retry_exceptions as exc:
            if attempt == attempts:
                raise
            if on_retry is not None:
                on_retry(attempt, exc)
            await asyncio.sleep(delay)
            delay *= 2

    raise RuntimeError("retry loop exited unexpectedly")
