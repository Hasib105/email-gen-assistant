"""Evidence sanitization before evidence crosses the LLM boundary."""

from __future__ import annotations

from email_assistant.domains.cases.schemas import CaseRecord
from email_assistant.domains.masking.service import PiiMasker
from email_assistant.domains.rag.retriever import Evidence


def sanitize_evidence_for_case(
    *,
    case: CaseRecord,
    evidence: list[Evidence],
    masker: PiiMasker,
) -> tuple[list[Evidence], list[str]]:
    """Return evidence with safe title/excerpt fields and detected placeholders."""
    known_values = case_sensitive_values(case)
    placeholders: set[str] = set()
    sanitized: list[Evidence] = []

    for item in evidence:
        title_result = masker.mask_text(item.title, known_values=known_values)
        excerpt_result = masker.mask_text(item.excerpt, known_values=known_values)
        placeholders.update(title_result.placeholder_map)
        placeholders.update(excerpt_result.placeholder_map)
        sanitized.append(
            item.model_copy(
                update={
                    "title": title_result.text,
                    "excerpt": excerpt_result.text,
                }
            )
        )

    return sanitized, sorted(placeholders)


def case_sensitive_values(case: CaseRecord) -> list[tuple[str, str]]:
    """Known case values that must never reach prompts or logs in raw form."""
    return [
        ("CUSTOMER", case.customer_name),
        ("BOOKING_REF", case.booking_reference),
        ("EMAIL", case.customer_email),
        ("PHONE", case.customer_phone),
    ]
