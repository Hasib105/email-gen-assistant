"""Draft response schemas."""

from __future__ import annotations

from case_assistant_api.domains.rag.retriever import Evidence
from pydantic import BaseModel, ConfigDict, Field


class DraftValidation(BaseModel):
    model_config = ConfigDict(frozen=True)

    complete: bool
    human_review_required: bool
    warnings: list[str] = Field(default_factory=list)


class DraftResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    safe_case_reference: str
    itinerary_draft: str
    customer_summary: str = ""

    # Structured reply fields — populated when the LLM supports structured output.
    reply_subject: str = ""
    reply_body: str = ""
    recommended_actions: list[str] = Field(default_factory=list)

    # Flat combined text kept for display and backward compatibility.
    customer_reply_draft: str

    evidence: list[Evidence]
    validation: DraftValidation
    masked_placeholders: list[str]
