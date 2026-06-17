"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Self

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _find_root_env_file() -> Path | None:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / ".env"
        if candidate.exists():
            return candidate
    return None


class Settings(BaseSettings):
    """Runtime configuration.

    Secrets are intentionally plain environment variables at scaffold stage.
    Production can replace this with a secrets manager without changing domain code.
    """

    model_config = SettingsConfigDict(
        env_file=_find_root_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    env: str = "development"
    app_env: str = ""
    log_level: str = "info"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    admin_api_key: str = ""

    database_url: str = "sqlite:///./email_assistant.db"
    database_ssl_mode: str = "disable"
    database_pool_min_size: int = 1
    database_pool_max_size: int = 10
    database_connect_timeout_seconds: float = 10.0
    database_command_timeout_seconds: float = 30.0
    case_repository_backend: str = "sqlite"
    case_table_name: str = "cases"
    evidence_stale_after_days: int = 365
    evidence_min_relevance_score: float = 1.0
    redis_url: str = "redis://localhost:6379/0"
    job_executor_backend: str = "background"
    job_store_backend: str = "memory"
    job_max_attempts: int = 3
    job_worker_concurrency: int = 4
    email_job_timeout_seconds: float = 120.0
    opensearch_url: str = "http://localhost:9200"
    opensearch_index: str = "email-assistant-evidence"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "email_assistant_evidence"
    rag_backend: str = "none"
    integration_retry_attempts: int = 3
    retrieval_timeout_seconds: float = 5.0

    langgraph_sqlite_path: str = ".logs/langgraph-checkpoints.sqlite"
    langgraph_postgres_url: str = ""

    llm_provider: str = "gemini"
    llm_model: str = "gemini-3.1-flash-lite"
    email_llm_timeout_seconds: float = 0.0
    email_llm_max_output_tokens: int = 1200
    response_language: str = "English"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    nvidia_api_key: str = ""
    pii_restore_approved: bool = False

    @field_validator("api_cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def environment(self: Self) -> str:
        return (self.app_env or self.env or "development").strip().lower()

    @property
    def is_production(self: Self) -> bool:
        return self.environment in {"production", "prod"}

    @property
    def uses_postgres_storage(self: Self) -> bool:
        return (
            self.case_repository_backend.lower().strip() == "postgres"
            or self.job_store_backend.lower().strip() == "postgres"
        )

    @property
    def langgraph_checkpoint_postgres_url(self: Self) -> str:
        """Postgres URL for LangGraph checkpoints.

        Uses ``LANGGRAPH_POSTGRES_URL`` only when explicitly set. ``DATABASE_URL``
        may point at the application database while local development still uses
        SQLite checkpoints.
        """
        return self.langgraph_postgres_url.strip()

    def validate_startup_safety(self: Self) -> None:
        """Fail fast on configuration that would make production unsafe."""
        if not self.is_production:
            return

        problems: list[str] = []
        if self.case_repository_backend.lower().strip() != "postgres":
            problems.append("CASE_REPOSITORY_BACKEND=postgres is required in production")
        if self.rag_backend.lower().strip() not in {"opensearch", "qdrant", "hybrid"}:
            problems.append("RAG_BACKEND must be opensearch, qdrant, or hybrid in production")
        if self.job_store_backend.lower().strip() != "postgres":
            problems.append("JOB_STORE_BACKEND=postgres is required in production")
        if self.job_executor_backend.lower().strip() != "arq":
            problems.append("JOB_EXECUTOR_BACKEND=arq is required in production")
        if self.database_ssl_mode.strip().lower() in {"", "disable", "off", "false"}:
            problems.append("DATABASE_SSL_MODE must be enabled in production")

        if problems:
            raise ValueError("Unsafe production configuration: " + "; ".join(problems))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
