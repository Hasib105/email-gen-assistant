from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from case_assistant_api.config import Settings
from case_assistant_api.domains.cases.schemas import CaseNotFoundError, CaseRecord, FlightSegment
from case_assistant_api.domains.drafts.validation import (
    assess_evidence_quality,
    detect_conflicting_evidence,
    validate_draft_grounding,
    validate_itinerary_consistency,
    validate_policy_claims,
)
from case_assistant_api.domains.rag.retriever import Evidence


def _sample_case() -> CaseRecord:
    return CaseRecord(
        case_id="CASE-1001",
        customer_name="Test Customer",
        customer_email="test@example.com",
        customer_phone="+15555550123",
        customer_tier="Gold",
        booking_reference="ABC123",
        issue_type="flight_disruption",
        summary="Flight delayed overnight.",
        requested_outcome="Rebook and hotel support.",
        itinerary=[
            FlightSegment(
                origin="NRT",
                destination="SIN",
                flight_number="JL711",
                departure_date="2026-06-10",
                status="delayed",
            )
        ],
    )


class _MissingCaseRepository:
    async def setup(self) -> None:
        return None

    async def get_case(self, case_id: str) -> CaseRecord:
        raise CaseNotFoundError(case_id=case_id.strip().upper())


@pytest.mark.asyncio
async def test_case_not_found_raises_clear_error() -> None:
    repository = _MissingCaseRepository()
    with pytest.raises(CaseNotFoundError) as exc_info:
        await repository.get_case("CASE-404")
    assert exc_info.value.case_id == "CASE-404"


def test_empty_evidence_adds_review_warning() -> None:
    warnings = assess_evidence_quality([], settings=Settings())
    assert warnings == ["No SOP or history evidence was retrieved."]


def test_stale_evidence_adds_warning() -> None:
    stale_time = (datetime.now(UTC) - timedelta(days=400)).isoformat()
    evidence = [
        Evidence(
            source="sop://old",
            title="Old policy",
            excerpt="Legacy guidance.",
            relevance_score=2.0,
            indexed_at=stale_time,
        )
    ]
    warnings = assess_evidence_quality(evidence, settings=Settings(evidence_stale_after_days=365))
    assert any("stale" in warning.lower() for warning in warnings)


def test_conflicting_evidence_adds_warning() -> None:
    evidence = [
        Evidence(
            source="sop://refund-yes",
            title="Refund allowed",
            excerpt="Offer a full refund when disruption exceeds six hours.",
        ),
        Evidence(
            source="sop://refund-no",
            title="No refund",
            excerpt="This fare is non-refundable and no refund should be promised.",
        ),
    ]
    warnings = detect_conflicting_evidence(evidence)
    assert warnings
    assert "conflicting evidence" in warnings[0].lower()


def test_policy_claim_without_evidence_is_flagged() -> None:
    evidence = [
        Evidence(
            source="sop://general",
            title="General support",
            excerpt="Acknowledge the request and provide next steps.",
        )
    ]
    warnings = validate_policy_claims(
        evidence=evidence,
        reply_subject="Refund update",
        reply_body="We have approved your full refund.",
        recommended_actions=[],
    )
    assert any("refund" in warning.lower() for warning in warnings)


def test_itinerary_conflict_is_flagged() -> None:
    case = _sample_case()
    warnings = validate_itinerary_consistency(
        case=case,
        itinerary_draft="Current itinerary context:\n- JL711: NRT to HKG on 2026-06-10",
        reply_body="Your JL711 flight from NRT to HKG remains delayed.",
    )
    assert warnings
    assert "conflict" in warnings[0].lower()


def test_validate_draft_grounding_combines_checks() -> None:
    case = _sample_case()
    warnings = validate_draft_grounding(
        case=case,
        evidence=[],
        itinerary_draft="",
        reply_subject="Refund approved",
        reply_body="We will refund and rebook your itinerary to HKG.",
        recommended_actions=["Issue voucher"],
        settings=Settings(),
    )
    assert any("no sop" in warning.lower() for warning in warnings)
    assert any("refund" in warning.lower() for warning in warnings)
