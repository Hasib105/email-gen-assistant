"""Health service."""

from __future__ import annotations

from case_assistant_api.config import get_settings
from case_assistant_api.domains.health.schemas import HealthCheck, HealthResponse


async def collect_health() -> HealthResponse:
    settings = get_settings()
    checks = [
        HealthCheck(name="api", ok=True),
        HealthCheck(name="postgres_configured", ok=bool(settings.database_url)),
        HealthCheck(name="redis_configured", ok=bool(settings.redis_url)),
        HealthCheck(name="opensearch_configured", ok=bool(settings.opensearch_url)),
        HealthCheck(name="qdrant_configured", ok=bool(settings.qdrant_url)),
    ]
    return HealthResponse(
        status="ok" if all(check.ok for check in checks) else "degraded",
        service="case-assistant-api",
        env=settings.env,
        checks=checks,
    )
