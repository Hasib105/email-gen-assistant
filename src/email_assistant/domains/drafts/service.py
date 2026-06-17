"""Draft generation service."""

from __future__ import annotations

from email_assistant.agents.drafts.graph import DraftGraphAgent
from email_assistant.domains.cases.repository import CaseRepository
from email_assistant.domains.drafts.schemas import DraftResponse
from email_assistant.domains.masking.service import PiiMasker
from email_assistant.domains.rag.retriever import EvidenceRetriever


class DraftService:
    def __init__(
        self,
        case_repository: CaseRepository | None = None,
        retriever: EvidenceRetriever | None = None,
        masker: PiiMasker | None = None,
        agent: DraftGraphAgent | None = None,
    ) -> None:
        self._agent = agent or DraftGraphAgent(
            case_repository=case_repository,
            retriever=retriever,
            masker=masker,
        )

    async def generate_for_case(self, case_id: str, user_question: str = "") -> DraftResponse:
        return await self._agent.generate_for_case(case_id, user_question=user_question)
