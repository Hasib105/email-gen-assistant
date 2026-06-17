"""Draft worker entrypoints."""

from __future__ import annotations

from case_assistant_api.domains.drafts.schemas import DraftResponse
from case_assistant_api.domains.drafts.service import DraftService


async def generate_case_draft_job(case_id: str) -> DraftResponse:
    service = DraftService()
    return await service.generate_for_case(case_id)
