"""LangGraph agent for AI-powered case draft generation."""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import cast
from uuid import uuid4

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from email_assistant.agents.drafts.checkpoints import open_draft_checkpointer
from email_assistant.agents.drafts.prompts import build_customer_reply_prompt
from email_assistant.agents.drafts.reply_schema import CaseDraftReply
from email_assistant.agents.drafts.state import DraftGraphContext, DraftGraphState
from email_assistant.agents.llm import get_llm
from email_assistant.config import Settings, get_settings
from email_assistant.domains.cases.repository import (
    CaseRepository,
    build_case_repository,
)
from email_assistant.domains.cases.schemas import CaseRecord
from email_assistant.domains.drafts.schemas import DraftResponse, DraftValidation
from email_assistant.domains.drafts.validation import validate_draft_grounding
from email_assistant.domains.masking.service import PiiMasker
from email_assistant.domains.rag.retriever import (
    Evidence,
    EvidenceRetriever,
    build_retriever,
)
from email_assistant.domains.rag.sanitization import sanitize_evidence_for_case
from email_assistant.security.output_guardrails import sanitize_generated_output

logger = structlog.get_logger()

type DraftStateGraph = StateGraph[
    DraftGraphState,
    DraftGraphContext,
    DraftGraphState,
    DraftGraphState,
]


class DraftGraphAgent:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        case_repository: CaseRepository | None = None,
        retriever: EvidenceRetriever | None = None,
        masker: PiiMasker | None = None,
        llm: object | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._case_repository = case_repository or build_case_repository(self._settings)
        self._retriever = retriever or build_retriever(self._settings)
        self._masker = masker or PiiMasker()
        self._llm = llm or get_llm(self._settings)

    async def generate_for_case(
        self,
        case_id: str,
        *,
        user_question: str = "",
        request_id: str | None = None,
        actor_reference: str = "user",
    ) -> DraftResponse:
        normalized_case_id = case_id.strip().upper()
        thread_id = f"case-draft:{normalized_case_id}:{request_id or uuid4().hex}"
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        context = DraftGraphContext(
            request_id=request_id or thread_id,
            actor_reference=actor_reference,
            settings=self._settings,
            case_repository=self._case_repository,
            retriever=self._retriever,
            masker=self._masker,
            llm=cast("BaseChatModel | None", self._llm),
        )

        async with open_draft_checkpointer(self._settings) as checkpointer:
            graph = get_draft_graph().compile(checkpointer=checkpointer)
            state = await graph.ainvoke(
                {"case_id": normalized_case_id, "user_question": user_question},
                config=config,
                context=context,
            )

        return DraftResponse(
            case_id=cast("str", state.get("case_id", "")),
            safe_case_reference=cast("str", state.get("safe_case_reference", "")),
            itinerary_draft=cast("str", state.get("itinerary_draft", "")),
            customer_summary=cast("str", state.get("customer_summary", "")),
            reply_subject=cast("str", state.get("reply_subject", "")),
            reply_body=cast("str", state.get("reply_body", "")),
            recommended_actions=cast("list[str]", state.get("recommended_actions", [])),
            customer_reply_draft=cast("str", state.get("customer_reply_draft", "")),
            evidence=cast("list[Evidence]", state.get("evidence", [])),
            validation=DraftValidation(
                complete=len(cast("list[str]", state.get("warnings", []))) == 0,
                human_review_required=True,
                warnings=cast("list[str]", state.get("warnings", [])),
            ),
            masked_placeholders=cast("list[str]", state.get("masked_placeholders", [])),
        )


@lru_cache(maxsize=1)
def get_draft_graph() -> DraftStateGraph:
    builder = StateGraph(DraftGraphState, context_schema=DraftGraphContext)
    builder.add_node("load_and_mask_case", load_and_mask_case)
    builder.add_node("build_prompt", build_prompt)
    builder.add_node("draft_reply", draft_reply)
    builder.add_node("validate", validate)
    builder.add_edge(START, "load_and_mask_case")
    builder.add_edge("load_and_mask_case", "build_prompt")
    builder.add_edge("build_prompt", "draft_reply")
    builder.add_edge("draft_reply", "validate")
    builder.add_edge("validate", END)
    return builder


async def load_and_mask_case(
    state: DraftGraphState,
    runtime: Runtime[DraftGraphContext],
) -> DraftGraphState:
    case = await runtime.context.case_repository.get_case(state.get("case_id", ""))
    runtime.context.loaded_case = case
    raw_evidence = await runtime.context.retriever.retrieve(case)
    evidence, evidence_placeholders = sanitize_evidence_for_case(
        case=case,
        evidence=raw_evidence,
        masker=runtime.context.masker,
    )
    masked_context, placeholders = mask_case_context(
        case=case,
        evidence=evidence,
        masker=runtime.context.masker,
    )
    all_placeholders = sorted({*placeholders, *evidence_placeholders})
    _ = runtime.context.actor_reference
    return {
        "case_id": case.case_id,
        "safe_case_reference": f"{case.case_id[:4]}-{case.case_id[-4:]}",
        "masked_context": masked_context,
        "masked_placeholders": all_placeholders,
        "evidence": evidence,
        "itinerary_draft": build_itinerary_draft(case),
        "customer_summary": build_customer_summary(case=case, masker=runtime.context.masker),
    }


async def build_prompt(
    state: DraftGraphState,
    runtime: Runtime[DraftGraphContext],
) -> DraftGraphState:
    settings = runtime.context.settings or get_settings()
    return {
        "prompt": build_customer_reply_prompt(
            masked_context=state.get("masked_context", ""),
            evidence=state.get("evidence", []),
            user_question=state.get("user_question", ""),
            response_language=settings.response_language,
        )
    }


async def draft_reply(
    state: DraftGraphState,
    runtime: Runtime[DraftGraphContext],
) -> DraftGraphState:
    """Call the LLM with structured output and return a typed CaseDraftReply."""
    prompt_text = state.get("prompt", "")
    logger.info("draft_reply_calling_llm", prompt_length=len(prompt_text))

    timeout_seconds = (runtime.context.settings or get_settings()).email_llm_timeout_seconds
    llm = runtime.context.llm or get_llm(runtime.context.settings or get_settings())
    structured_llm = llm.with_structured_output(CaseDraftReply)
    try:
        invocation = structured_llm.ainvoke([HumanMessage(content=prompt_text)])
        result = cast(
            "CaseDraftReply",
            await asyncio.wait_for(invocation, timeout=timeout_seconds)
            if timeout_seconds > 0
            else await invocation,
        )
        generation_mode = "llm"
    except TimeoutError as exc:
        logger.warning(
            "draft_reply_llm_timeout",
            timeout_seconds=timeout_seconds,
            prompt_length=len(prompt_text),
        )
        raise RuntimeError("LLM response timed out before producing a draft.") from exc

    logger.info(
        "draft_reply_complete",
        subject=_safe_log_text(result.subject),
        actions_count=len(result.recommended_actions),
        generation_mode=generation_mode,
    )
    return _draft_reply_state(result=result, generation_mode=generation_mode)


def _draft_reply_state(
    *,
    result: CaseDraftReply,
    generation_mode: str,
) -> DraftGraphState:
    combined = f"Subject: {result.subject}\n\n{result.body}"
    return {
        "customer_reply_draft": combined,
        "reply_subject": result.subject,
        "reply_body": result.body,
        "recommended_actions": result.recommended_actions,
        "draft_generation_mode": generation_mode,
    }


def _safe_log_text(value: str) -> str:
    return value.encode("ascii", errors="backslashreplace").decode("ascii")


async def validate(
    state: DraftGraphState,
    runtime: Runtime[DraftGraphContext],
) -> DraftGraphState:
    warnings: list[str] = list(state.get("warnings", []))
    itinerary_draft = state.get("itinerary_draft", "")
    evidence = state.get("evidence", [])
    settings = runtime.context.settings or get_settings()

    case = runtime.context.loaded_case
    if case is None:
        case = await runtime.context.case_repository.get_case(state.get("case_id", ""))
    if not itinerary_draft.strip():
        warnings.append("No itinerary was available for review.")

    warnings.extend(
        validate_draft_grounding(
            case=case,
            evidence=evidence,
            itinerary_draft=itinerary_draft,
            reply_subject=state.get("reply_subject", ""),
            reply_body=state.get("reply_body", ""),
            recommended_actions=state.get("recommended_actions", []),
            settings=settings,
        )
    )

    guarded = sanitize_generated_output(
        case=case,
        masker=runtime.context.masker,
        reply_subject=state.get("reply_subject", ""),
        reply_body=state.get("reply_body", ""),
        recommended_actions=state.get("recommended_actions", []),
        itinerary_draft=itinerary_draft,
    )
    warnings.extend(guarded.warnings)
    existing_placeholders: list[str] = state.get("masked_placeholders", [])
    masked_placeholders: list[str] = sorted(
        {*existing_placeholders, *guarded.detected_placeholders}
    )
    customer_reply_draft = (
        f"Subject: {guarded.reply_subject}\n\n{guarded.reply_body}"
        if guarded.reply_subject or guarded.reply_body
        else state.get("customer_reply_draft", "")
    )
    return {
        "warnings": warnings,
        "reply_subject": guarded.reply_subject,
        "reply_body": guarded.reply_body,
        "recommended_actions": guarded.recommended_actions,
        "itinerary_draft": guarded.itinerary_draft,
        "customer_reply_draft": customer_reply_draft,
        "masked_placeholders": masked_placeholders,
    }


def mask_case_context(
    *,
    case: CaseRecord,
    evidence: list[Evidence],
    masker: PiiMasker,
) -> tuple[str, list[str]]:
    evidence_titles = ", ".join(item.title for item in evidence)

    # Build a rich context block including preferences and travel history.
    prefs = case.travel_preferences
    pref_summary = (
        (
            f"seat preference: {prefs.preferred_seat}, "
            f"meal: {prefs.meal_preference}, "
            f"preferred airlines: {', '.join(prefs.preferred_airlines) or 'none'}, "
            f"hotel chain: {prefs.preferred_hotel_chain}. "
            f"Notes: {prefs.notes}"
        )
        if (prefs.preferred_seat or prefs.meal_preference)
        else "no preferences on file"
    )

    history_lines = (
        "; ".join(
            f"{h.origin}→{h.destination} on {h.date} ({h.status})"
            for h in case.travel_history[-3:]  # include last 3 trips
        )
        or "no previous travel history"
    )

    safe_summary = (
        f"Case {case.case_id} for {case.customer_name} ({case.customer_email}, "
        f"{case.customer_phone}) — {case.customer_tier} tier — "
        f"booking ref {case.booking_reference}. "
        f"Issue: {case.summary} "
        f"Requested outcome: {case.requested_outcome}. "
        f"Travel preferences: {pref_summary}. "
        f"Recent travel history: {history_lines}. "
        f"Relevant guidance: {evidence_titles}."
    )
    masking = masker.mask_text(
        safe_summary,
        known_values=[
            ("CUSTOMER", case.customer_name),
            ("BOOKING_REF", case.booking_reference),
            ("EMAIL", case.customer_email),
            ("PHONE", case.customer_phone),
        ],
    )
    return masking.text, sorted(masking.placeholder_map)


def build_customer_summary(*, case: CaseRecord, masker: PiiMasker) -> str:
    """Build a masked operator-facing customer summary for display."""
    prefs = case.travel_preferences
    pref_parts: list[str] = []
    if prefs.preferred_seat:
        pref_parts.append(f"seat: {prefs.preferred_seat}")
    if prefs.meal_preference:
        pref_parts.append(f"meal: {prefs.meal_preference}")
    if prefs.preferred_airlines:
        pref_parts.append(f"airlines: {', '.join(prefs.preferred_airlines)}")
    if prefs.preferred_hotel_chain:
        pref_parts.append(f"hotel: {prefs.preferred_hotel_chain}")
    if prefs.notes:
        pref_parts.append(f"notes: {prefs.notes}")
    preferences = "; ".join(pref_parts) if pref_parts else "none on file"

    history = (
        "; ".join(
            f"{entry.origin}→{entry.destination} on {entry.date} ({entry.status})"
            for entry in case.travel_history[-3:]
        )
        or "none on file"
    )

    raw_summary = (
        f"Customer: {case.customer_name}\n"
        f"Tier: {case.customer_tier}\n"
        f"Email: {case.customer_email}\n"
        f"Phone: {case.customer_phone}\n"
        f"Booking: {case.booking_reference}\n"
        f"Issue: {case.issue_type} — {case.summary}\n"
        f"Requested outcome: {case.requested_outcome}\n"
        f"Preferences: {preferences}\n"
        f"Recent travel: {history}"
    )
    masking = masker.mask_text(
        raw_summary,
        known_values=[
            ("CUSTOMER", case.customer_name),
            ("BOOKING_REF", case.booking_reference),
            ("EMAIL", case.customer_email),
            ("PHONE", case.customer_phone),
        ],
    )
    return masking.text


def build_itinerary_draft(case: CaseRecord) -> str:
    if not case.itinerary:
        return "No itinerary segments were available in the case data."
    segments = [
        f"{segment.flight_number}: {segment.origin} to {segment.destination} "
        f"on {segment.departure_date} ({segment.status})"
        for segment in case.itinerary
    ]
    return "Current itinerary context:\n" + "\n".join(f"- {segment}" for segment in segments)
