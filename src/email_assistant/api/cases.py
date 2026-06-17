"""Case draft routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from email_assistant.domains.cases.schemas import CaseNotFoundError
from email_assistant.domains.drafts.schemas import DraftResponse
from email_assistant.domains.drafts.service import DraftService

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("/{case_id}/draft", summary="Generate a human-review draft for a case")
async def draft_case(case_id: str) -> DraftResponse:
    service = DraftService()
    try:
        return await service.generate_for_case(case_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
