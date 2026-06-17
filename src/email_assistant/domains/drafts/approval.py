"""Draft review state for human approval workflows.

All draft approval state is persisted in PostgreSQL via ``PostgresDraftApprovalStore``.
There is no in-memory fallback — every environment uses the database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from functools import lru_cache
from typing import Any, Protocol

import orjson
from case_assistant_api.config import get_settings
from case_assistant_api.db.pool import get_pool
from case_assistant_api.domains.drafts.schemas import DraftResponse


def _now() -> datetime:
    return datetime.now(UTC)


class DraftApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


@dataclass(frozen=True)
class DraftAuditEvent:
    event_type: str
    case_id: str
    user_id: str
    created_at: datetime = field(default_factory=_now)
    note: str = ""


@dataclass(frozen=True)
class StoredDraft:
    case_id: str
    draft: DraftResponse
    status: DraftApprovalStatus
    created_by: str
    created_at: datetime
    updated_at: datetime
    approved_by: str = ""
    approved_at: datetime | None = None
    review_notes: str = ""
    audit_events: tuple[DraftAuditEvent, ...] = ()


class DraftApprovalStore(Protocol):
    """Interface for draft approval persistence."""

    async def save_pending(self, draft: DraftResponse, *, user_id: str) -> StoredDraft: ...
    async def save_edited(self, draft: DraftResponse, *, user_id: str) -> StoredDraft: ...
    async def approve(self, case_id: str, *, user_id: str) -> StoredDraft | None: ...
    async def reject(self, case_id: str, *, user_id: str, note: str = "") -> StoredDraft | None: ...
    async def record_event(
        self,
        case_id: str,
        *,
        event_type: str,
        user_id: str,
        note: str = "",
    ) -> StoredDraft | None: ...
    async def get(self, case_id: str) -> StoredDraft | None: ...
    async def clear(self) -> None: ...


# ── PostgreSQL schema ────────────────────────────────────────────────────────

_DRAFT_APPROVAL_TABLE = "draft_approvals"
_DRAFT_AUDIT_TABLE = "draft_audit_events"

_SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS {_DRAFT_APPROVAL_TABLE} (
    case_id        text PRIMARY KEY,
    draft          jsonb NOT NULL,
    status         text NOT NULL DEFAULT 'pending',
    created_by     text NOT NULL,
    created_at     timestamptz NOT NULL,
    updated_at     timestamptz NOT NULL,
    approved_by    text NOT NULL DEFAULT '',
    approved_at    timestamptz,
    review_notes   text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS {_DRAFT_AUDIT_TABLE} (
    id             bigserial PRIMARY KEY,
    case_id        text NOT NULL REFERENCES {_DRAFT_APPROVAL_TABLE}(case_id),
    event_type     text NOT NULL,
    user_id        text NOT NULL,
    created_at     timestamptz NOT NULL,
    note           text NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_draft_audit_case_id
    ON {_DRAFT_AUDIT_TABLE}(case_id);
"""


def _serialize_draft(draft: DraftResponse) -> str:
    return orjson.dumps(draft.model_dump()).decode()


def _deserialize_draft(raw: object) -> DraftResponse:
    if isinstance(raw, str):
        return DraftResponse.model_validate(orjson.loads(raw))
    if isinstance(raw, bytes | bytearray):
        return DraftResponse.model_validate(orjson.loads(raw))
    if isinstance(raw, dict):
        return DraftResponse.model_validate(raw)
    raise ValueError(f"Cannot deserialize draft payload: {type(raw)}")


def _parse_tz(value: object) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    raise ValueError(f"Expected datetime, got {type(value)}")


def _parse_optional_tz(value: object) -> datetime | None:
    if value is None:
        return None
    return _parse_tz(value)


def _row_to_stored_draft(row: Any, events: list[DraftAuditEvent]) -> StoredDraft:
    return StoredDraft(
        case_id=row["case_id"],
        draft=_deserialize_draft(row["draft"]),
        status=DraftApprovalStatus(row["status"]),
        created_by=row["created_by"],
        created_at=_parse_tz(row["created_at"]),
        updated_at=_parse_tz(row["updated_at"]),
        approved_by=row["approved_by"] or "",
        approved_at=_parse_optional_tz(row["approved_at"]),
        review_notes=row["review_notes"] or "",
        audit_events=tuple(events),
    )


# ── PostgreSQL store ─────────────────────────────────────────────────────────


class PostgresDraftApprovalStore:
    """PostgreSQL-backed draft approval store.

    Expected table shapes::

        draft_approvals(
            case_id    text primary key,
            draft      jsonb not null,
            status     text not null default 'pending',
            created_by text not null,
            created_at timestamptz not null,
            updated_at timestamptz not null,
            approved_by text not null default '',
            approved_at timestamptz,
            review_notes text not null default ''
        )

        draft_audit_events(
            id         bigserial primary key,
            case_id    text not null references draft_approvals(case_id),
            event_type text not null,
            user_id    text not null,
            created_at timestamptz not null,
            note       text not null default ''
        )
    """

    def __init__(self, *, database_url: str) -> None:
        self._database_url = database_url

    async def setup(self) -> None:
        """Create tables if they do not exist."""
        connection = await self._connect()
        try:
            await connection.execute(_SCHEMA_SQL)
        finally:
            await self._release(connection)

    async def save_pending(self, draft: DraftResponse, *, user_id: str) -> StoredDraft:
        now = _now()
        case_id = draft.case_id.upper()
        draft_json = _serialize_draft(draft)
        connection = await self._connect()
        try:
            await connection.execute(
                f"""
                INSERT INTO {_DRAFT_APPROVAL_TABLE}
                    (case_id, draft, status, created_by, created_at, updated_at)
                VALUES ($1, $2::jsonb, $3, $4, $5, $6)
                ON CONFLICT (case_id) DO UPDATE SET
                    draft = EXCLUDED.draft,
                    status = EXCLUDED.status,
                    updated_at = EXCLUDED.updated_at
                """,
                case_id,
                draft_json,
                DraftApprovalStatus.PENDING,
                user_id,
                now,
                now,
            )
            await connection.execute(
                f"""
                INSERT INTO {_DRAFT_AUDIT_TABLE} (case_id, event_type, user_id, created_at, note)
                VALUES ($1, $2, $3, $4, '')
                """,
                case_id,
                "draft_generated",
                user_id,
                now,
            )
        finally:
            await self._release(connection)
        return await self._require_loaded(case_id)

    async def save_edited(self, draft: DraftResponse, *, user_id: str) -> StoredDraft:
        now = _now()
        case_id = draft.case_id.upper()
        draft_json = _serialize_draft(draft)
        connection = await self._connect()
        try:
            existing = await connection.fetchrow(
                f"SELECT case_id FROM {_DRAFT_APPROVAL_TABLE} WHERE case_id = $1",
                case_id,
            )
            if existing is not None:
                await connection.execute(
                    f"""
                    UPDATE {_DRAFT_APPROVAL_TABLE}
                    SET draft = $2::jsonb, status = $3, updated_at = $4
                    WHERE case_id = $1
                    """,
                    case_id,
                    draft_json,
                    DraftApprovalStatus.EDITED,
                    now,
                )
            else:
                await connection.execute(
                    f"""
                    INSERT INTO {_DRAFT_APPROVAL_TABLE}
                        (case_id, draft, status, created_by, created_at, updated_at)
                    VALUES ($1, $2::jsonb, $3, $4, $5, $6)
                    """,
                    case_id,
                    draft_json,
                    DraftApprovalStatus.EDITED,
                    user_id,
                    now,
                    now,
                )
            await connection.execute(
                f"""
                INSERT INTO {_DRAFT_AUDIT_TABLE} (case_id, event_type, user_id, created_at, note)
                VALUES ($1, $2, $3, $4, '')
                """,
                case_id,
                "draft_edited",
                user_id,
                now,
            )
        finally:
            await self._release(connection)
        return await self._require_loaded(case_id)

    async def approve(self, case_id: str, *, user_id: str) -> StoredDraft | None:
        now = _now()
        normalized = case_id.upper()
        connection = await self._connect()
        try:
            existing = await connection.fetchrow(
                f"SELECT case_id FROM {_DRAFT_APPROVAL_TABLE} WHERE case_id = $1",
                normalized,
            )
            if existing is None:
                return None
            await connection.execute(
                f"""
                UPDATE {_DRAFT_APPROVAL_TABLE}
                SET status = $2, approved_by = $3, approved_at = $4, updated_at = $4
                WHERE case_id = $1
                """,
                normalized,
                DraftApprovalStatus.APPROVED,
                user_id,
                now,
            )
            await connection.execute(
                f"""
                INSERT INTO {_DRAFT_AUDIT_TABLE} (case_id, event_type, user_id, created_at, note)
                VALUES ($1, $2, $3, $4, '')
                """,
                normalized,
                "draft_approved",
                user_id,
                now,
            )
        finally:
            await self._release(connection)
        return await self._load(normalized)

    async def reject(self, case_id: str, *, user_id: str, note: str = "") -> StoredDraft | None:
        now = _now()
        normalized = case_id.upper()
        connection = await self._connect()
        try:
            existing = await connection.fetchrow(
                f"SELECT case_id FROM {_DRAFT_APPROVAL_TABLE} WHERE case_id = $1",
                normalized,
            )
            if existing is None:
                return None
            await connection.execute(
                f"""
                UPDATE {_DRAFT_APPROVAL_TABLE}
                SET status = $2, review_notes = $3, updated_at = $4
                WHERE case_id = $1
                """,
                normalized,
                DraftApprovalStatus.REJECTED,
                note,
                now,
            )
            await connection.execute(
                f"""
                INSERT INTO {_DRAFT_AUDIT_TABLE} (case_id, event_type, user_id, created_at, note)
                VALUES ($1, $2, $3, $4, $5)
                """,
                normalized,
                "draft_rejected",
                user_id,
                now,
                note,
            )
        finally:
            await self._release(connection)
        return await self._load(normalized)

    async def record_event(
        self,
        case_id: str,
        *,
        event_type: str,
        user_id: str,
        note: str = "",
    ) -> StoredDraft | None:
        now = _now()
        normalized = case_id.upper()
        connection = await self._connect()
        try:
            existing = await connection.fetchrow(
                f"SELECT case_id FROM {_DRAFT_APPROVAL_TABLE} WHERE case_id = $1",
                normalized,
            )
            if existing is None:
                return None
            await connection.execute(
                f"""
                INSERT INTO {_DRAFT_AUDIT_TABLE} (case_id, event_type, user_id, created_at, note)
                VALUES ($1, $2, $3, $4, $5)
                """,
                normalized,
                event_type,
                user_id,
                now,
                note,
            )
            await connection.execute(
                f"UPDATE {_DRAFT_APPROVAL_TABLE} SET updated_at = $2 WHERE case_id = $1",
                normalized,
                now,
            )
        finally:
            await self._release(connection)
        return await self._load(normalized)

    async def get(self, case_id: str) -> StoredDraft | None:
        return await self._load(case_id.upper())

    async def clear(self) -> None:
        connection = await self._connect()
        try:
            await connection.execute(f"DELETE FROM {_DRAFT_AUDIT_TABLE}")
            await connection.execute(f"DELETE FROM {_DRAFT_APPROVAL_TABLE}")
        finally:
            await self._release(connection)

    async def _load(self, case_id: str) -> StoredDraft | None:
        connection = await self._connect()
        try:
            row = await connection.fetchrow(
                f"SELECT * FROM {_DRAFT_APPROVAL_TABLE} WHERE case_id = $1",
                case_id,
            )
            if row is None:
                return None
            event_rows = await connection.fetch(
                f"""
                SELECT event_type, case_id, user_id, created_at, note
                FROM {_DRAFT_AUDIT_TABLE}
                WHERE case_id = $1
                ORDER BY id
                """,
                case_id,
            )
        finally:
            await self._release(connection)
        events = [
            DraftAuditEvent(
                event_type=e["event_type"],
                case_id=e["case_id"],
                user_id=e["user_id"],
                created_at=_parse_tz(e["created_at"]),
                note=e["note"] or "",
            )
            for e in event_rows
        ]
        return _row_to_stored_draft(row, events)

    async def _require_loaded(self, case_id: str) -> StoredDraft:
        stored = await self._load(case_id)
        if stored is None:
            raise RuntimeError(f"Draft approval record for {case_id} was not found after write")
        return stored

    async def _connect(self) -> Any:
        pool = get_pool()
        return await pool.acquire()

    async def _release(self, connection: Any) -> None:
        pool = get_pool()
        await pool.release(connection)


# ── Singleton ────────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_draft_approval_store() -> PostgresDraftApprovalStore:
    """Return the PostgreSQL-backed approval store.

    The database URL comes from ``Settings.database_url`` at first call.
    Call ``get_draft_approval_store.cache_clear()`` to reset.
    """
    return PostgresDraftApprovalStore(database_url=get_settings().database_url)
