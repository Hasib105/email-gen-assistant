"""Async connection pool with SQLite fallback when PostgreSQL is unavailable."""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib import import_module
from pathlib import Path
from typing import Any

import structlog

from email_assistant.config import Settings, get_settings

logger = structlog.get_logger()

_pool: Any | None = None
_sqlite_conn: Any | None = None
_is_sqlite: bool = False


def _is_sqlite_url(url: str) -> bool:
    return url.startswith("sqlite")


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
    global _pool, _sqlite_conn, _is_sqlite  # noqa: PLW0603
    if _pool is not None or _sqlite_conn is not None:
        return _pool or _sqlite_conn

    resolved = settings or get_settings()

    if _is_sqlite_url(resolved.database_url):
        aiosqlite = import_module("aiosqlite")
        db_path = resolved.database_url.removeprefix("sqlite:///")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _sqlite_conn = await aiosqlite.connect(db_path)
        _sqlite_conn.row_factory = sqlite3.Row
        await _sqlite_conn.execute("PRAGMA journal_mode=WAL")
        await _sqlite_conn.execute("PRAGMA foreign_keys=ON")
        _is_sqlite = True
        logger.info("sqlite_database_opened", path=db_path)
        return _sqlite_conn

    asyncpg_module = import_module("asyncpg")
    create_pool = asyncpg_module.create_pool
    _pool = await create_pool(
        resolved.database_url,
        min_size=resolved.database_pool_min_size,
        max_size=resolved.database_pool_max_size,
        **_connect_kwargs(resolved),
    )
    _is_sqlite = False
    logger.info(
        "database_pool_opened",
        min_size=resolved.database_pool_min_size,
        max_size=resolved.database_pool_max_size,
        ssl_mode=resolved.database_ssl_mode,
    )
    return _pool


async def close_pool() -> None:
    global _pool, _sqlite_conn, _is_sqlite  # noqa: PLW0603
    if _sqlite_conn is not None:
        await _sqlite_conn.close()
        _sqlite_conn = None
        _is_sqlite = False
        logger.info("sqlite_database_closed")
        return
    if _pool is None:
        return
    await _pool.close()
    _pool = None
    logger.info("database_pool_closed")


def get_pool() -> Any:
    if _is_sqlite and _sqlite_conn is not None:
        return _sqlite_conn
    if _pool is None:
        raise RuntimeError("Database pool is not open. Call open_pool() during startup.")
    return _pool


def is_sqlite_mode() -> bool:
    return _is_sqlite


@asynccontextmanager
async def get_connection() -> AsyncGenerator[Any]:
    if _is_sqlite and _sqlite_conn is not None:
        yield _sqlite_conn
        return
    pool = get_pool()
    async with pool.acquire() as connection:
        yield connection
