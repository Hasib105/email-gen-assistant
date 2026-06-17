from __future__ import annotations

from typing import Any

import pytest
from email_assistant.config import Settings
from email_assistant.domains.rag.indexer import EvidenceIndexService
from email_assistant.domains.rag.retriever import Evidence


class _FakeResponse:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None


@pytest.mark.asyncio
async def test_evidence_indexer_stores_seed_catalog_in_opensearch_and_qdrant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, dict[str, Any]]] = []

    class FakeClient:
        def __init__(self, *, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def put(self, url: str, json: dict[str, Any]) -> _FakeResponse:
            calls.append(("PUT", url, json))
            return _FakeResponse()

    monkeypatch.setattr("email_assistant.domains.rag.indexer.httpx.AsyncClient", FakeClient)

    service = EvidenceIndexService(
        Settings(
            rag_backend="hybrid",
            opensearch_url="http://opensearch:9200",
            qdrant_url="http://qdrant:6333",
            retrieval_timeout_seconds=2.0,
            integration_retry_attempts=1,
        )
    )

    results = await service.index_evidence(
        [
            Evidence(
                source="sop://flight-disruption/rebooking",
                title="Same-day disruption rebooking",
                excerpt="Offer same-day alternatives first.",
                tags=["flight_disruption", "rebooking", "sop"],
            ),
            Evidence(
                source="sop://customer-tier/gold",
                title="Gold tier support handling",
                excerpt="Gold customers should receive proactive next-step language.",
                tags=["gold", "customer_tier", "sop"],
            ),
            Evidence(
                source="sop://general/support-draft",
                title="General support draft",
                excerpt="Acknowledge the request and give a reviewable next step.",
                tags=["general", "support", "sop"],
            ),
        ]
    )

    assert {result.backend for result in results} == {"opensearch", "qdrant"}
    assert all(result.ok for result in results)
    assert any(call[1] == "http://opensearch:9200/email-assistant-evidence" for call in calls)
    assert any(
        call[1] == "http://qdrant:6333/collections/email_assistant_evidence/points" for call in calls
    )
    qdrant_points = next(
        call[2]["points"]
        for call in calls
        if call[1] == "http://qdrant:6333/collections/email_assistant_evidence/points"
    )
    assert len(qdrant_points) == 3
