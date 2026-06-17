"""FastAPI application factory and ASGI entrypoint."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import (
    AgentScalarConfig,
    get_scalar_api_reference,  # pyright: ignore[reportUnknownVariableType]
)
from starlette.responses import HTMLResponse

from email_assistant.api.admin import router as admin_router
from email_assistant.api.cases import router as cases_router
from email_assistant.api.emails import router as emails_router
from email_assistant.api.health import router as health_router
from email_assistant.config import get_settings
from email_assistant.db.migrations import run_migrations
from email_assistant.db.pool import close_pool, is_sqlite_mode, open_pool
from email_assistant.domains.cases.repository import build_case_repository
from email_assistant.domains.drafts.approval import get_draft_approval_store
from email_assistant.domains.jobs.store import get_job_store
from email_assistant.observability.logging import configure_logging
from email_assistant.workers.dispatch import close_arq_pool

logger = structlog.get_logger()


async def _setup_durable_stores() -> None:
    settings = get_settings()
    await open_pool(settings)
    await run_migrations()

    if not is_sqlite_mode():
        case_repository = build_case_repository(settings)
        await case_repository.setup()

    await get_job_store().setup()
    await get_draft_approval_store().setup()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = get_settings()
    settings.validate_startup_safety()
    configure_logging(settings.log_level)
    await _setup_durable_stores()
    yield
    await close_arq_pool()
    await close_pool()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Email Generation Assistant API",
        version="0.1.0",
        description="AI-powered email generation assistant with advanced prompt engineering and evaluation metrics.",
        lifespan=lifespan,
        debug=not settings.is_production,
    )
    if settings.api_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.api_cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(health_router)
    app.include_router(admin_router)
    app.include_router(cases_router)
    app.include_router(emails_router)
    app.add_api_route(
        "/scalar",
        build_scalar_api_reference(app.openapi_url),
        methods=["GET"],
        include_in_schema=False,
    )
    return app


def build_scalar_api_reference(openapi_url: str | None) -> Callable[[], HTMLResponse]:
    def scalar_api_reference() -> HTMLResponse:
        return get_scalar_api_reference(
            openapi_url=openapi_url,
            title="Email Generation Assistant API Reference",
            agent=AgentScalarConfig(disabled=True),
        )

    return scalar_api_reference


app = create_app()
