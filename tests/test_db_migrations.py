from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from email_assistant.db.migrations import run_migrations


@pytest.mark.asyncio
async def test_run_migrations_applies_sql_once(monkeypatch: pytest.MonkeyPatch) -> None:
    executed: list[str] = []
    existing_versions: set[str] = set()

    class FakeConnection:
        async def executescript(self, sql: str) -> None:
            executed.append(sql)

        async def execute(self, sql: str, *args: object) -> None:
            _ = args
            executed.append(sql)

        async def fetchall(self) -> list[tuple[str]]:
            return [(version,) for version in existing_versions]

        async def commit(self) -> None:
            return None

    @asynccontextmanager
    async def fake_get_connection():
        yield FakeConnection()

    monkeypatch.setattr("email_assistant.db.pool.get_connection", fake_get_connection)
    monkeypatch.setattr("email_assistant.db.pool._is_sqlite", True)

    applied = await run_migrations()
    assert applied == ["001_initial_schema"]
    existing_versions.add("001_initial_schema")

    applied_again = await run_migrations()
    assert applied_again == []
    assert any("schema_migrations" in sql for sql in executed)
    assert any("CREATE TABLE IF NOT EXISTS cases" in sql for sql in executed)
