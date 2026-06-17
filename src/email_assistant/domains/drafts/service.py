"""Draft generation service."""

from __future__ import annotations

from case_assistant_api.agents.drafts.graph import DraftGraphAgent
from case_assistant_api.domains.cases.repository import CaseRepository
from case_assistant_api.domains.drafts.schemas import DraftResponse
from case_assistant_api.domains.masking.service import PiiMasker
from case_assistant_api.domains.rag.retriever import EvidenceRetriever


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
