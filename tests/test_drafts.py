from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from email_assistant.agents import drafts as drafts_pkg
from email_assistant.agents.drafts.reply_schema import CaseDraftReply
from email_assistant.config import Settings, get_settings
from email_assistant.domains.drafts.service import DraftService
from repository_fixtures import SeedCaseRepository, SeedEvidenceRetriever


def _patch_llm(
    monkeypatch: pytest.MonkeyPatch,
    subject: str = "Case Update",
    body: str = "Dear CUSTOMER_1, we are reviewing your case.",
    actions: list[str] | None = None,
) -> None:
    """Patch get_llm so tests never make real network calls.

    The fake LLM supports with_structured_output() and returns a CaseDraftReply.
    """
    monkeypatch.setenv("DRAFT_LLM_TIMEOUT_SECONDS", "4.0")
    get_settings.cache_clear()

    result = CaseDraftReply(
        subject=subject,
        body=body,
        recommended_actions=actions or [],
    )
    fake_structured = MagicMock()
    fake_structured.ainvoke = AsyncMock(return_value=result)

    fake_llm = MagicMock()
    fake_llm.with_structured_output = MagicMock(return_value=fake_structured)

    def _get_fake_llm(settings: Settings | None = None) -> MagicMock:
        _ = settings
        return fake_llm

    monkeypatch.setattr(
        "email_assistant.agents.drafts.graph.get_llm",
        _get_fake_llm,
    )


@pytest.mark.asyncio
async def test_draft_generation_is_human_review_only_and_masked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_llm(monkeypatch, body="Dear CUSTOMER_1, the support team will review your case.")

    draft = await DraftService(
        case_repository=SeedCaseRepository(),
        retriever=SeedEvidenceRetriever(),
    ).generate_for_case("case-1001")

    assert draft.case_id == "CASE-1001"
    assert draft.validation.human_review_required is True
    assert draft.validation.complete is True
    assert draft.evidence
    assert "Yuki Tanaka" not in draft.customer_reply_draft
    assert "TYO9X7" not in draft.customer_reply_draft
    assert "CUSTOMER_1" in draft.masked_placeholders
    assert "BOOKING_REF_1" in draft.masked_placeholders


@pytest.mark.asyncio
async def test_draft_generation_returns_structured_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_llm(
        monkeypatch,
        subject="Rebooking Update for BOOKING_REF_1",
        body="Dear CUSTOMER_1, three same-day options are available.",
        actions=["Check ANA/JAL flights CTS to HND", "Confirm hotel voucher eligibility"],
    )

    draft = await DraftService(
        case_repository=SeedCaseRepository(),
        retriever=SeedEvidenceRetriever(),
    ).generate_for_case("case-1001")

    assert draft.reply_subject == "Rebooking Update for BOOKING_REF_1"
    assert "same-day" in draft.reply_body.lower()
    assert len(draft.recommended_actions) == 2
    # customer_reply_draft must combine subject + body
    assert "Subject:" in draft.customer_reply_draft
    assert draft.reply_body in draft.customer_reply_draft


@pytest.mark.asyncio
async def test_draft_generation_with_user_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_llm(
        monkeypatch,
        body="There are three same-day rebooking options available.",
    )

    draft = await DraftService(
        case_repository=SeedCaseRepository(),
        retriever=SeedEvidenceRetriever(),
    ).generate_for_case(
        "case-1001", user_question="What are the same-day rebooking options?"
    )

    assert draft.case_id == "CASE-1001"
    assert "rebooking" in draft.reply_body.lower()


# Ensure the drafts package resolves correctly (smoke-test import).
_ = drafts_pkg
