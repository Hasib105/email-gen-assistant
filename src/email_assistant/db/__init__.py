"""Shared database infrastructure for production PostgreSQL/Aurora."""

from email_assistant.db.migrations import run_migrations
from email_assistant.db.pool import close_pool, get_connection, get_pool, open_pool

__all__ = [
    "close_pool",
    "get_connection",
    "get_pool",
    "open_pool",
    "run_migrations",
]
