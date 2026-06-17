"""Versioned SQL migrations with PostgreSQL and SQLite support."""

from __future__ import annotations

from importlib import resources

import structlog

from email_assistant.db.pool import get_connection, is_sqlite_mode

logger = structlog.get_logger()

_MIGRATIONS_PACKAGE = "email_assistant.db.migrations_sql"

_SQLITE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cases (
    case_id        TEXT PRIMARY KEY,
    issue_type     TEXT NOT NULL DEFAULT 'general',
    customer_tier  TEXT NOT NULL DEFAULT '',
    payload        TEXT NOT NULL DEFAULT '{}',
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS background_jobs (
    job_id         TEXT PRIMARY KEY,
    job_type       TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'queued',
    case_id        TEXT NOT NULL,
    payload        TEXT NOT NULL DEFAULT '{}',
    attempts       INTEGER NOT NULL DEFAULT 0,
    max_attempts   INTEGER NOT NULL DEFAULT 3,
    error          TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    started_at     TEXT,
    finished_at    TEXT
);

CREATE TABLE IF NOT EXISTS draft_approvals (
    case_id        TEXT PRIMARY KEY,
    draft          TEXT NOT NULL DEFAULT '{}',
    status         TEXT NOT NULL DEFAULT 'pending',
    created_by     TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    approved_by    TEXT NOT NULL DEFAULT '',
    approved_at    TEXT,
    review_notes   TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS draft_audit_events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id        TEXT NOT NULL REFERENCES draft_approvals(case_id),
    event_type     TEXT NOT NULL,
    user_id        TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    note           TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


async def run_migrations() -> list[str]:
    """Apply pending SQL migrations and return the applied version names."""
    if is_sqlite_mode():
        return await _run_sqlite_migrations()
    return await _run_postgres_migrations()


async def _run_sqlite_migrations() -> list[str]:
    applied: list[str] = []
    async with get_connection() as connection:
        await connection.executescript(_SQLITE_SCHEMA_SQL)
        cursor = await connection.execute("SELECT version FROM schema_migrations")
        rows = await cursor.fetchall()
        existing = {row[0] for row in rows}

        for version, sql in _load_migration_files():
            if version in existing:
                continue
            await connection.executescript(sql)
            await connection.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)",
                (version,),
            )
            await connection.commit()
            applied.append(version)
            logger.info("database_migration_applied", version=version)

    return applied


async def _run_postgres_migrations() -> list[str]:
    applied: list[str] = []
    async with get_connection() as connection:
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version text PRIMARY KEY,
                applied_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        existing_rows = await connection.fetch("SELECT version FROM schema_migrations")
        existing = {row["version"] for row in existing_rows}

        for version, sql in _load_migration_files():
            if version in existing:
                continue
            async with connection.transaction():
                await connection.execute(sql)
                await connection.execute(
                    "INSERT INTO schema_migrations (version) VALUES ($1)",
                    version,
                )
            applied.append(version)
            logger.info("database_migration_applied", version=version)

    return applied


def _load_migration_files() -> list[tuple[str, str]]:
    migrations: list[tuple[str, str]] = []
    package = resources.files(_MIGRATIONS_PACKAGE)
    for path in sorted(package.iterdir(), key=lambda item: item.name):
        if not path.name.endswith(".sql"):
            continue
        version = path.name.removesuffix(".sql")
        migrations.append((version, path.read_text(encoding="utf-8")))
    return migrations
