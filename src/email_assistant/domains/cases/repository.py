"""Case repositories backed by PostgreSQL."""

from __future__ import annotations

from typing import Protocol, cast

import orjson
from case_assistant_api.config import Settings
from case_assistant_api.db.pool import get_connection
from case_assistant_api.domains.cases.schemas import CaseNotFoundError, CaseRecord

_DEFAULT_CASE_TABLE = "cases"


class CaseRepository(Protocol):
    async def setup(self) -> None: ...

    async def get_case(self, case_id: str) -> CaseRecord: ...


class PostgresCaseRepository:
    """Production PostgreSQL/Aurora case repository."""

    def __init__(self, *, database_url: str, table_name: str = _DEFAULT_CASE_TABLE) -> None:
        self._database_url = database_url
        self._table_name = validate_identifier(table_name)

    async def setup(self) -> None:
        return None

    async def get_case(self, case_id: str) -> CaseRecord:
        normalized = case_id.strip().upper()
        query = f"""
            SELECT payload
            FROM {self._table_name}
            WHERE case_id = $1
        """
        async with get_connection() as connection:
            row = await connection.fetchrow(query, normalized)

        if row is None:
            raise CaseNotFoundError(case_id=normalized)

        payload = _coerce_payload(row["payload"])
        return CaseRecord.model_validate(payload)


def build_case_repository(settings: Settings) -> CaseRepository:
    backend = settings.case_repository_backend.lower().strip()
    if backend != "postgres":
        raise ValueError(
            f"Unsupported CASE_REPOSITORY_BACKEND={backend!r}. "
            "Use 'postgres' and seed data with scripts/seed.py."
        )
    return PostgresCaseRepository(
        database_url=settings.database_url,
        table_name=settings.case_table_name,
    )


def validate_identifier(value: str) -> str:
    if not value or not value.replace("_", "").isalnum() or value[0].isdigit():
        raise ValueError("Postgres identifier must contain only letters, digits, and underscores")
    return value


def _coerce_payload(payload: object) -> dict[str, object]:
    if isinstance(payload, dict):
        return cast("dict[str, object]", payload)
    if isinstance(payload, str | bytes | bytearray):
        decoded: object = orjson.loads(payload)
        if isinstance(decoded, dict):
            return cast("dict[str, object]", decoded)
    raise ValueError("Case payload must be a JSON object")
