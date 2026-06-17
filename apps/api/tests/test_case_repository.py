from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from case_assistant_api.config import Settings
from case_assistant_api.domains.cases.repository import (
    PostgresCaseRepository,
    build_case_repository,
)


@pytest.mark.asyncio
async def test_postgres_case_repository_loads_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    payload = {
        "case_id": "CASE-2001",
        "customer_name": "Test Customer",
        "customer_email": "test@example.com",
        "customer_phone": "+15555550123",
        "customer_tier": "Silver",
        "booking_reference": "ABC123",
        "issue_type": "general",
        "summary": "Needs itinerary help.",
        "requested_outcome": "Send options.",
    }

    class FakeConnection:
        async def fetchrow(self, query: str, case_id: str) -> dict[str, object]:
            calls.append((query, case_id))
            return {"payload": payload}

    @asynccontextmanager
    async def fake_get_connection():
        yield FakeConnection()

    monkeypatch.setattr(
        "case_assistant_api.domains.cases.repository.get_connection",
        fake_get_connection,
    )

    repository = PostgresCaseRepository(
        database_url="postgresql://local/test",
        table_name="cases",
    )
    case = await repository.get_case("case-2001")

    assert case.case_id == "CASE-2001"
    assert "CASE-2001" in calls[0][1]


def test_build_case_repository_rejects_non_postgres_backend() -> None:
    with pytest.raises(ValueError, match="Unsupported CASE_REPOSITORY_BACKEND"):
        build_case_repository(Settings(case_repository_backend="fixture"))


def test_build_case_repository_rejects_unsafe_table_name() -> None:
    with pytest.raises(ValueError):
        build_case_repository(
            Settings(
                case_repository_backend="postgres",
                case_table_name="cases;drop",
            )
        )
