from __future__ import annotations

from collections.abc import Iterator

import pytest
from case_assistant_api.config import get_settings
from case_assistant_api.domains.drafts.approval import get_draft_approval_store
from case_assistant_api.domains.jobs.store import get_job_store


@pytest.fixture(autouse=True)
def isolate_runtime_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep local .env files from changing test safety assumptions."""
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setenv("LANGGRAPH_POSTGRES_URL", "")
    monkeypatch.setenv("JOB_STORE_BACKEND", "memory")
    monkeypatch.setenv("JOB_EXECUTOR_BACKEND", "background")
    monkeypatch.setenv("INTEGRATION_RETRY_ATTEMPTS", "1")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-api-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-api-key")
    monkeypatch.delenv("APP_ENV", raising=False)
    get_settings.cache_clear()
    get_job_store.cache_clear()
    get_draft_approval_store.cache_clear()
    yield
    get_draft_approval_store.cache_clear()
    get_job_store.cache_clear()
    get_settings.cache_clear()
