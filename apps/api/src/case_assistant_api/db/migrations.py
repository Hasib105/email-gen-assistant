"""Versioned SQL migrations for production PostgreSQL/Aurora."""

from __future__ import annotations

from importlib import resources

import structlog

from case_assistant_api.db.pool import get_connection

logger = structlog.get_logger()

_MIGRATIONS_PACKAGE = "case_assistant_api.db.migrations_sql"


async def run_migrations() -> list[str]:
    """Apply pending SQL migrations and return the applied version names."""
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
