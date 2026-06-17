from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from email_assistant.agents.drafts.checkpoints import open_draft_checkpointer
from email_assistant.agents.drafts.graph import DraftGraphAgent, get_draft_graph
from email_assistant.agents.drafts.prompts import build_customer_reply_prompt
from email_assistant.agents.drafts.reply_schema import CaseDraftReply
from email_assistant.config import Settings
from email_assistant.domains.cases.schemas import CaseRecord
from email_assistant.domains.rag.retriever import Evidence
from repository_fixtures import SeedCaseRepository, SeedEvidenceRetriever


def _make_fake_llm(
    subject: str = "Flight Disruption Update",
    body: str = "Dear CUSTOMER_1, we are reviewing your case.",
    actions: list[str] | None = None,
) -> object:
    """Return a fake LLM that supports with_structured_output()."""
    result = CaseDraftReply(
        subject=subject,
        body=body,
        recommended_actions=actions or ["Review rebooking options"],
    )
    fake_structured = MagicMock()
    fake_structured.ainvoke = AsyncMock(return_value=result)

    fake_llm = MagicMock()
    fake_llm.with_structured_output = MagicMock(return_value=fake_structured)
    return fake_llm


class EmptyRetriever:
    async def retrieve(self, case: CaseRecord) -> list[Evidence]:
        _ = case
        return []


def _graph_agent(
    *,
    settings: Settings,
    llm: object,
    retriever: object | None = None,
) -> DraftGraphAgent:
    return DraftGraphAgent(
        settings=settings,
        case_repository=SeedCaseRepository(),
        retriever=retriever or SeedEvidenceRetriever(),
        llm=llm,
    )


@pytest.mark.asyncio
async def test_draft_graph_uses_sqlite_checkpointer_without_raw_customer_data(
    tmp_path: Path,
) -> None:
    agent = _graph_agent(
        settings=Settings(
            database_url="",

            email_llm_timeout_seconds=4.0,
            langgraph_sqlite_path=str(tmp_path / "checkpoints.sqlite"),
        ),
        llm=_make_fake_llm(),
    )

    draft = await agent.generate_for_case(
        "CASE-1001",
        request_id="test-run",
        actor_reference="U123",
    )

    assert draft.case_id == "CASE-1001"
    assert "Yuki Tanaka" not in draft.customer_reply_draft
    assert "yuki.tanaka@example.jp" not in draft.customer_reply_draft
    assert "TYO9X7" not in draft.customer_reply_draft
    assert "CUSTOMER_1" in draft.masked_placeholders
    assert (tmp_path / "checkpoints.sqlite").exists()


@pytest.mark.asyncio
async def test_draft_graph_returns_structured_fields(
    tmp_path: Path,
) -> None:
    agent = _graph_agent(
        settings=Settings(
            database_url="",

            email_llm_timeout_seconds=4.0,
            langgraph_sqlite_path=str(tmp_path / "checkpoints.sqlite"),
        ),
        llm=_make_fake_llm(
            subject="Same-Day Rebooking for BOOKING_REF_1",
            body="Dear CUSTOMER_1, we have found same-day options.",
            actions=["Check AA/DL availability", "Verify hotel voucher"],
        ),
    )

    draft = await agent.generate_for_case("CASE-1001", request_id="test-struct")

    assert draft.reply_subject == "Same-Day Rebooking for BOOKING_REF_1"
    assert draft.reply_body == "Dear CUSTOMER_1, we have found same-day options."
    assert "CUSTOMER_1" in draft.customer_summary
    assert "Gold" in draft.customer_summary
    assert "Yuki Tanaka" not in draft.customer_summary
    assert len(draft.recommended_actions) == 2
    assert "Subject: Same-Day Rebooking" in draft.customer_reply_draft


@pytest.mark.asyncio
async def test_draft_graph_masks_generated_pii_and_requires_review(
    tmp_path: Path,
) -> None:
    agent = _graph_agent(
        settings=Settings(
            database_url="",

            email_llm_timeout_seconds=4.0,
            langgraph_sqlite_path=str(tmp_path / "checkpoints.sqlite"),
        ),
        llm=_make_fake_llm(
            subject="Update for TYO9X7",
            body="Dear Yuki Tanaka, we emailed yuki.tanaka@example.jp.",
            actions=["Call +81 90-1234-5678 about booking TYO9X7."],
        ),
    )

    draft = await agent.generate_for_case("CASE-1001", request_id="test-output-guard")

    rendered = draft.model_dump_json()
    assert "Yuki Tanaka" not in rendered
    assert "yuki.tanaka@example.jp" not in rendered
    assert "+81 90-1234-5678" not in rendered
    assert "TYO9X7" not in rendered
    assert "CUSTOMER_1" in rendered
    assert "EMAIL_1" in rendered
    assert "PHONE_1" in rendered
    assert "BOOKING_REF_1" in rendered
    assert draft.validation.complete is False
    assert draft.validation.human_review_required is True
    assert any("raw sensitive data" in warning for warning in draft.validation.warnings)


@pytest.mark.asyncio
async def test_draft_graph_surfaces_missing_evidence_when_retrieval_is_empty(
    tmp_path: Path,
) -> None:
    agent = _graph_agent(
        settings=Settings(
            database_url="",

            email_llm_timeout_seconds=4.0,
            langgraph_sqlite_path=str(tmp_path / "checkpoints.sqlite"),
        ),
        retriever=EmptyRetriever(),
        llm=_make_fake_llm(),
    )

    draft = await agent.generate_for_case("CASE-1001", request_id="test-empty-evidence")

    assert draft.evidence == []
    assert any("no sop" in warning.lower() for warning in draft.validation.warnings)


@pytest.mark.asyncio
async def test_draft_graph_passes_user_question_to_prompt(
    tmp_path: Path,
) -> None:
    captured_prompts: list[str] = []

    result = CaseDraftReply(
        subject="Rebooking Options",
        body="Here are the rebooking options.",
        recommended_actions=[],
    )

    fake_structured = MagicMock()

    async def _ainvoke(messages: list[Any], **_: object) -> CaseDraftReply:
        for msg in messages:
            if hasattr(msg, "content"):
                captured_prompts.append(str(msg.content))
        return result

    fake_structured.ainvoke = _ainvoke

    fake_llm = MagicMock()
    fake_llm.with_structured_output = MagicMock(return_value=fake_structured)

    agent = _graph_agent(
        settings=Settings(
            database_url="",

            email_llm_timeout_seconds=4.0,
            langgraph_sqlite_path=str(tmp_path / "checkpoints.sqlite"),
        ),
        llm=fake_llm,
    )

    await agent.generate_for_case(
        "CASE-1001",
        user_question="What are the rebooking options?",
        request_id="test-question",
    )

    assert captured_prompts, "LLM was not called"
    assert "rebooking" in captured_prompts[0].lower()


@pytest.mark.asyncio
async def test_draft_graph_passes_response_language_to_prompt(
    tmp_path: Path,
) -> None:
    captured_prompts: list[str] = []

    result = CaseDraftReply(
        subject="Rebooking Options",
        body="Here are the rebooking options.",
        recommended_actions=[],
    )

    fake_structured = MagicMock()

    async def _ainvoke(messages: list[Any], **_: object) -> CaseDraftReply:
        for msg in messages:
            if hasattr(msg, "content"):
                captured_prompts.append(str(msg.content))
        return result

    fake_structured.ainvoke = _ainvoke

    fake_llm = MagicMock()
    fake_llm.with_structured_output = MagicMock(return_value=fake_structured)

    agent = _graph_agent(
        settings=Settings(
            database_url="",

            email_llm_timeout_seconds=4.0,
            response_language="English",
            langgraph_sqlite_path=str(tmp_path / "checkpoints.sqlite"),
        ),
        llm=fake_llm,
    )

    await agent.generate_for_case("CASE-1001", request_id="test-language")

    assert captured_prompts, "LLM was not called"
    assert "Write the customer-facing reply in English." in captured_prompts[0]


@pytest.mark.asyncio
async def test_draft_graph_raises_when_llm_times_out(
    tmp_path: Path,
) -> None:
    fake_structured = MagicMock()

    async def _slow_ainvoke(messages: list[Any], **_: object) -> CaseDraftReply:
        assert messages
        await asyncio.sleep(1)
        return CaseDraftReply(
            subject="Too slow",
            body="This should not be used.",
            recommended_actions=[],
        )

    fake_structured.ainvoke = _slow_ainvoke
    fake_llm = MagicMock()
    fake_llm.with_structured_output = MagicMock(return_value=fake_structured)

    agent = _graph_agent(
        settings=Settings(
            database_url="",

            email_llm_timeout_seconds=0.01,
            langgraph_sqlite_path=str(tmp_path / "checkpoints.sqlite"),
        ),
        llm=fake_llm,
    )

    with pytest.raises(RuntimeError, match="LLM response timed out"):
        await agent.generate_for_case("CASE-1001", request_id="test-timeout")


@pytest.mark.asyncio
async def test_draft_graph_waits_for_llm_when_timeout_is_zero(
    tmp_path: Path,
) -> None:
    fake_llm = _make_fake_llm(
        subject="AI Required",
        body="Dear CUSTOMER_1, this came from the LLM.",
    )

    agent = _graph_agent(
        settings=Settings(
            database_url="",

            email_llm_timeout_seconds=0.0,
            langgraph_sqlite_path=str(tmp_path / "checkpoints.sqlite"),
        ),
        llm=fake_llm,
    )

    draft = await agent.generate_for_case("CASE-1001", request_id="test-fast-mode")

    cast("MagicMock", fake_llm).with_structured_output.assert_called_once()
    assert draft.reply_subject == "AI Required"
    assert "came from the LLM" in draft.reply_body
    assert draft.validation.warnings == []


@pytest.mark.asyncio
async def test_draft_checkpointer_uses_postgres_when_url_is_provided(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    class FakePostgresSaver:
        async def __aenter__(self) -> FakePostgresSaver:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def setup(self) -> None:
            return None

    def from_conn_string(conn_string: str) -> FakePostgresSaver:
        calls.append(conn_string)
        return FakePostgresSaver()

    monkeypatch.setattr(
        "email_assistant.agents.drafts.checkpoints.AsyncPostgresSaver.from_conn_string",
        from_conn_string,
    )

    async with open_draft_checkpointer(
        Settings(
            langgraph_postgres_url="postgresql://user:pass@localhost:5432/langgraph",
            langgraph_sqlite_path=str(tmp_path / "unused.sqlite"),
        )
    ):
        pass

    assert calls == ["postgresql://user:pass@localhost:5432/langgraph"]
    assert not (tmp_path / "unused.sqlite").exists()


@pytest.mark.asyncio
async def test_draft_checkpointer_uses_sqlite_when_postgres_checkpoint_url_is_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    class FakePostgresSaver:
        async def __aenter__(self) -> FakePostgresSaver:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def setup(self) -> None:
            return None

    def from_conn_string(conn_string: str) -> FakePostgresSaver:
        calls.append(conn_string)
        return FakePostgresSaver()

    monkeypatch.setattr(
        "email_assistant.agents.drafts.checkpoints.AsyncPostgresSaver.from_conn_string",
        from_conn_string,
    )

    async with open_draft_checkpointer(
        Settings(
            database_url="postgresql://email_assistant:email_assistant@localhost:5432/email_assistant",
            langgraph_postgres_url="",
            langgraph_sqlite_path=str(tmp_path / "checkpoints.sqlite"),
        )
    ):
        pass

    assert calls == []
    assert (tmp_path / "checkpoints.sqlite").exists()


def test_customer_reply_prompt_includes_question() -> None:
    prompt = build_customer_reply_prompt(
        masked_context="Case CASE-1001 for CUSTOMER_1 uses booking BOOKING_REF_1.",
        evidence=[
            Evidence(
                source="sop://test",
                title="Test guidance",
                excerpt="Use safe, reviewable wording.",
            )
        ],
        user_question="What rebooking options are available?",
    )

    assert "CUSTOMER_1" in prompt
    assert "BOOKING_REF_1" in prompt
    assert "Never reveal raw personal data" in prompt
    assert "Write the customer-facing reply in English." in prompt
    assert "rebooking" in prompt.lower()


def test_customer_reply_prompt_has_default_task_when_no_question() -> None:
    prompt = build_customer_reply_prompt(
        masked_context="Case CASE-1002 for CUSTOMER_1.",
        evidence=[],
        user_question="",
    )

    assert "next actions" in prompt.lower() or "summary" in prompt.lower()


def test_draft_graph_definition_is_cached() -> None:
    get_draft_graph.cache_clear()

    first = get_draft_graph()
    second = get_draft_graph()

    assert first is second
    assert get_draft_graph.cache_info().hits == 1
