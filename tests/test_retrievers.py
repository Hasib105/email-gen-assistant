from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest
from email_assistant.domains.cases.schemas import CaseRecord
from email_assistant.domains.rag.retriever import (
    Evidence,
    HybridEvidenceRetriever,
    OpenSearchRetriever,
    QdrantRetriever,
)


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
    )


class _FakeResponse:
    def __init__(self, body: dict[str, object]) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._body


@pytest.mark.asyncio
async def test_opensearch_retriever_maps_hits_to_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeClient:
        def __init__(self, *, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, json: dict[str, object]) -> _FakeResponse:
            calls.append((url, json))
            return _FakeResponse(
                {
                    "hits": {
                        "hits": [
                            {
                                "_source": {
                                    "source": "sop://flight",
                                    "title": "Flight disruption SOP",
                                    "excerpt": "Offer same-day alternatives first.",
                                }
                            }
                        ]
                    }
                }
            )

    monkeypatch.setattr("email_assistant.domains.rag.retriever.httpx.AsyncClient", FakeClient)

    case = _sample_case()
    retriever = OpenSearchRetriever(
        url="http://opensearch:9200",
        index_name="email-assistant-evidence",
        timeout_seconds=2.0,
        retry_attempts=1,
    )

    evidence = await retriever.retrieve(case)

    assert evidence[0].source == "sop://flight"
    assert evidence[0].title == "Flight disruption SOP"
    assert calls[0][0] == "http://opensearch:9200/email-assistant-evidence/_search"


@pytest.mark.asyncio
async def test_qdrant_retriever_maps_payloads_to_ranked_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    class FakeClient:
        def __init__(self, *, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, json: dict[str, Any]) -> _FakeResponse:
            calls.append((url, json))
            return _FakeResponse(
                {
                    "result": {
                        "points": [
                            {
                                "payload": {
                                    "source": "sop://generic",
                                    "title": "General support",
                                    "excerpt": "Acknowledge the request.",
                                }
                            },
                            {
                                "payload": {
                                    "source": "sop://flight-disruption",
                                    "title": "Flight disruption handling",
                                    "excerpt": "Use rebooking options for flight disruption cases.",
                                }
                            },
                        ]
                    }
                }
            )

    monkeypatch.setattr("email_assistant.domains.rag.retriever.httpx.AsyncClient", FakeClient)

    case = _sample_case()
    retriever = QdrantRetriever(
        url="http://qdrant:6333",
        collection_name="email_assistant_evidence",
        timeout_seconds=2.0,
        retry_attempts=1,
    )

    evidence = await retriever.retrieve(case)

    assert evidence[0].source == "sop://flight-disruption"
    assert calls[0][0] == "http://qdrant:6333/collections/email_assistant_evidence/points/scroll"
    assert calls[0][1]["with_payload"] is True


@pytest.mark.asyncio
async def test_hybrid_retriever_runs_backends_concurrently() -> None:
    class SlowRetriever:
        def __init__(self, source: str) -> None:
            self.source = source

        async def retrieve(self, case: CaseRecord) -> list[Evidence]:
            _ = case
            await asyncio.sleep(0.05)
            return [
                Evidence(
                    source=self.source,
                    title=f"{self.source} title",
                    excerpt="Relevant guidance.",
                )
            ]

    case = _sample_case()
    retriever = HybridEvidenceRetriever(
        [SlowRetriever("sop://a"), SlowRetriever("sop://b")],
    )

    start = time.perf_counter()
    evidence = await retriever.retrieve(case)
    elapsed = time.perf_counter() - start

    assert [item.source for item in evidence] == ["sop://a", "sop://b"]
    assert elapsed < 0.09
