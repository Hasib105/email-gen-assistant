"""Health routes."""

from __future__ import annotations

from fastapi import APIRouter

from case_assistant_api.domains.health.schemas import HealthResponse
from case_assistant_api.domains.health.service import collect_health

router = APIRouter(tags=["health"])


@router.get("/health", summary="Service health")
async def get_health() -> HealthResponse:
    return await collect_health()
