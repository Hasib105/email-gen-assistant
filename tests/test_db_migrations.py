from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from case_assistant_api.db.migrations import run_migrations


@pytest.mark.asyncio
async def test_run_migrations_applies_sql_once(monkeypatch: pytest.MonkeyPatch) -> None:
    executed: list[str] = []
    existing_versions: set[str] = set()

    class FakeConnection:
        async def execute(self, sql: str, *args: object) -> None:
            _ = args
            executed.append(sql)

        async def fetch(self, sql: str) -> list[dict[str, str]]:
            _ = sql
            return [{"version": version} for version in existing_versions]

        def transaction(self) -> _FakeTransaction:
            return _FakeTransaction()

    class _FakeTransaction:
        async def __aenter__(self) -> _FakeTransaction:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

    @asynccontextmanager
    async def fake_get_connection():
        yield FakeConnection()

    monkeypatch.setattr("case_assistant_api.db.migrations.get_connection", fake_get_connection)

    applied = await run_migrations()
    assert applied == ["001_initial_schema"]
    existing_versions.add("001_initial_schema")

    applied_again = await run_migrations()
    assert applied_again == []
    assert any("schema_migrations" in sql for sql in executed)
    assert any("CREATE TABLE IF NOT EXISTS cases" in sql for sql in executed)
