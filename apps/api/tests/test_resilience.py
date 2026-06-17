from __future__ import annotations

import pytest
from case_assistant_api.resilience import retry_async


@pytest.mark.asyncio
async def test_retry_async_retries_transient_failures() -> None:
    attempts = 0

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise TimeoutError("temporary")
        return "ok"

    result = await retry_async(
        operation,
        attempts=3,
        initial_delay_seconds=0,
        retry_exceptions=(TimeoutError,),
    )

    assert result == "ok"
    assert attempts == 3


@pytest.mark.asyncio
async def test_retry_async_raises_after_last_attempt() -> None:
    attempts = 0

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        raise TimeoutError("still broken")

    with pytest.raises(TimeoutError):
        await retry_async(
            operation,
            attempts=2,
            initial_delay_seconds=0,
            retry_exceptions=(TimeoutError,),
        )

    assert attempts == 2
