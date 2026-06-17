"""Asyncpg connection pool with production SSL and timeout settings."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib import import_module
from typing import Any

import structlog

from case_assistant_api.config import Settings, get_settings

logger = structlog.get_logger()

_pool: Any | None = None


def _ssl_context(settings: Settings) -> bool | str:
    mode = settings.database_ssl_mode.strip().lower()
    if mode in {"", "disable", "off", "false"}:
        return False
    if mode in {"require", "verify-ca", "verify-full"}:
        return mode
    return False


def _connect_kwargs(settings: Settings) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "command_timeout": settings.database_command_timeout_seconds,
        "timeout": settings.database_connect_timeout_seconds,
    }
    ssl = _ssl_context(settings)
    if ssl:
        kwargs["ssl"] = ssl
    return kwargs


async def open_pool(settings: Settings | None = None) -> Any:
    global _pool  # noqa: PLW0603
    if _pool is not None:
        return _pool

    resolved = settings or get_settings()
    asyncpg_module = import_module("asyncpg")
    create_pool = asyncpg_module.create_pool
    _pool = await create_pool(
        resolved.database_url,
        min_size=resolved.database_pool_min_size,
        max_size=resolved.database_pool_max_size,
        **_connect_kwargs(resolved),
    )
    logger.info(
        "database_pool_opened",
        min_size=resolved.database_pool_min_size,
        max_size=resolved.database_pool_max_size,
        ssl_mode=resolved.database_ssl_mode,
    )
    return _pool


async def close_pool() -> None:
    global _pool  # noqa: PLW0603
    if _pool is None:
        return
    await _pool.close()
    _pool = None
    logger.info("database_pool_closed")


def get_pool() -> Any:
    if _pool is None:
        raise RuntimeError("Database pool is not open. Call open_pool() during startup.")
    return _pool


@asynccontextmanager
async def get_connection() -> AsyncGenerator[Any]:
    pool = get_pool()
    async with pool.acquire() as connection:
        yield connection
