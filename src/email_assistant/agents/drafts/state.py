"""State and context for the case draft graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypedDict

from email_assistant.config import get_settings
from email_assistant.domains.cases.repository import (
    CaseRepository,
    build_case_repository,
)
from email_assistant.domains.cases.schemas import CaseRecord
from email_assistant.domains.masking.service import PiiMasker
from email_assistant.domains.rag.retriever import (
    Evidence,
    EvidenceRetriever,
    build_retriever,
)

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from email_assistant.config import Settings


class DraftGraphState(TypedDict, total=False):
    """Checkpointed graph state.

    Keep this free of raw customer/user identifiers. Store only masked or safe
    values because checkpointers persist this state.
    """

    case_id: str
    safe_case_reference: str
    masked_context: str
    masked_placeholders: list[str]
    evidence: list[Evidence]
    itinerary_draft: str
    customer_summary: str
    # Flat combined draft kept for backward compatibility.
    customer_reply_draft: str
    # Structured reply fields populated by the LLM structured-output node.
    reply_subject: str
    reply_body: str
    recommended_actions: list[str]
    draft_generation_mode: str
    warnings: list[str]
    prompt: str
    user_question: str


@dataclass
class DraftGraphContext:
    """Runtime-only context that is never checkpointed."""

    request_id: str
    actor_reference: str = "user"
    case_repository: CaseRepository = field(
        default_factory=lambda: build_case_repository(get_settings())
    )
    retriever: EvidenceRetriever = field(default_factory=lambda: build_retriever(get_settings()))
    masker: PiiMasker = field(default_factory=PiiMasker)
    # Settings and LLM are injected here so individual nodes stay pure functions.
    # Pass an explicit llm in tests to avoid real network calls.
    settings: Settings | None = None
    llm: BaseChatModel | None = None
    loaded_case: CaseRecord | None = field(default=None, repr=False)
