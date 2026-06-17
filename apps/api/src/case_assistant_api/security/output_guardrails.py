"""Guardrails for AI-generated text before operator-facing output."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from case_assistant_api.domains.cases.schemas import CaseRecord
from case_assistant_api.domains.masking.service import PiiMasker
from case_assistant_api.domains.rag.sanitization import case_sensitive_values


class GuardedDraftOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    reply_subject: str
    reply_body: str
    recommended_actions: list[str]
    itinerary_draft: str
    warnings: list[str] = Field(default_factory=list)
    detected_placeholders: list[str] = Field(default_factory=list)


def sanitize_generated_output(
    *,
    case: CaseRecord,
    masker: PiiMasker,
    reply_subject: str,
    reply_body: str,
    recommended_actions: list[str],
    itinerary_draft: str,
) -> GuardedDraftOutput:
    """Mask generated content and warn when raw sensitive data was detected."""
    known_values = case_sensitive_values(case)
    placeholders: set[str] = set()

    subject_result = masker.mask_text(reply_subject, known_values=known_values)
    body_result = masker.mask_text(reply_body, known_values=known_values)
    itinerary_result = masker.mask_text(itinerary_draft, known_values=known_values)
    placeholders.update(subject_result.placeholder_map)
    placeholders.update(body_result.placeholder_map)
    placeholders.update(itinerary_result.placeholder_map)

    safe_actions: list[str] = []
    for action in recommended_actions:
        action_result = masker.mask_text(action, known_values=known_values)
        placeholders.update(action_result.placeholder_map)
        safe_actions.append(action_result.text)

    warnings = (
        ["Generated content contained raw sensitive data and was masked before review."]
        if placeholders
        else []
    )

    return GuardedDraftOutput(
        reply_subject=subject_result.text,
        reply_body=body_result.text,
        recommended_actions=safe_actions,
        itinerary_draft=itinerary_result.text,
        warnings=warnings,
        detected_placeholders=sorted(placeholders),
    )
