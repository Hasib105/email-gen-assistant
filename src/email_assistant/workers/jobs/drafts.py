"""Draft worker entrypoints."""

from __future__ import annotations

from email_assistant.domains.drafts.schemas import DraftResponse
from email_assistant.domains.drafts.service import DraftService


async def generate_case_draft_job(case_id: str) -> DraftResponse:
    service = DraftService()
    return await service.generate_for_case(case_id)
