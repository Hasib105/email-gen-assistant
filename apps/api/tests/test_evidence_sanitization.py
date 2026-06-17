from __future__ import annotations

from case_assistant_api.agents.drafts.prompts import build_customer_reply_prompt
from case_assistant_api.domains.cases.schemas import CaseRecord
from case_assistant_api.domains.masking.service import PiiMasker
from case_assistant_api.domains.rag.retriever import Evidence
from case_assistant_api.domains.rag.sanitization import sanitize_evidence_for_case


def _case() -> CaseRecord:
    return CaseRecord(
        case_id="CASE-1001",
        customer_name="Yuki Tanaka",
        customer_email="yuki.tanaka@example.jp",
        customer_phone="+81 90-1234-5678",
        customer_tier="Gold",
        booking_reference="TYO9X7",
        issue_type="flight_disruption",
        summary="Customer is stranded.",
        requested_outcome="Find rebooking.",
    )


def test_evidence_excerpts_are_sanitized_before_prompt_construction() -> None:
    evidence = [
        Evidence(
            source="history://case-1001",
            title="Conversation with Yuki Tanaka",
            excerpt=(
                "Yuki Tanaka emailed yuki.tanaka@example.jp from +81 90-1234-5678. "
                "Booking ref TYO9X7. Passport AB1234567. "
                "Allergy: peanuts. Health condition: asthma. Religion: Shinto."
            ),
        )
    ]

    sanitized, placeholders = sanitize_evidence_for_case(
        case=_case(),
        evidence=evidence,
        masker=PiiMasker(),
    )
    prompt = build_customer_reply_prompt(
        masked_context="Case CASE-1001 for CUSTOMER_1.",
        evidence=sanitized,
    )

    assert "Yuki Tanaka" not in prompt
    assert "yuki.tanaka@example.jp" not in prompt
    assert "+81 90-1234-5678" not in prompt
    assert "TYO9X7" not in prompt
    assert "AB1234567" not in prompt
    assert "peanuts" not in prompt
    assert "asthma" not in prompt
    assert "Shinto" not in prompt
    assert {"CUSTOMER_1", "EMAIL_1", "PHONE_1", "BOOKING_REF_1"}.issubset(set(placeholders))
    assert "PASSPORT_1" in placeholders
    assert "ALLERGY_1" in prompt
    assert "HEALTH_1" in prompt
    assert "RELIGION_1" in prompt
