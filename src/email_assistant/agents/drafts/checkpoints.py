"""Checkpointer factory for draft graphs."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from email_assistant.config import Settings


@asynccontextmanager
async def open_draft_checkpointer(
    settings: Settings,
) -> AsyncGenerator[BaseCheckpointSaver[str]]:
    postgres_url = settings.langgraph_checkpoint_postgres_url
    if postgres_url:
        async with AsyncPostgresSaver.from_conn_string(postgres_url) as checkpointer:
            await checkpointer.setup()
            yield checkpointer
        return

    sqlite_path = _resolve_sqlite_path(settings.langgraph_sqlite_path)
    async with AsyncSqliteSaver.from_conn_string(str(sqlite_path)) as checkpointer:
        await checkpointer.setup()
        yield checkpointer


def _resolve_sqlite_path(path: str) -> Path:
    sqlite_path = Path(path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite_path
