"""RAG retrieval seam."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Protocol, cast
from urllib.parse import quote

import httpx
import structlog
from email_assistant.config import Settings
from email_assistant.domains.cases.schemas import CaseRecord
from email_assistant.resilience import retry_async
from pydantic import BaseModel, ConfigDict, Field

logger = structlog.get_logger()

MIN_QUERY_TERM_LENGTH = 4


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    title: str
    excerpt: str
    tags: list[str] = Field(default_factory=list)
    issue_type: str = ""
    relevance_score: float = 0.0
    indexed_at: str | None = None


class EvidenceRetriever(Protocol):
    async def retrieve(self, case: CaseRecord) -> list[Evidence]: ...


class OpenSearchRetriever:
    """Retrieve SOP/history evidence from an OpenSearch index."""

    def __init__(
        self,
        *,
        url: str,
        index_name: str,
        timeout_seconds: float,
        retry_attempts: int,
        limit: int = 5,
        min_score: float = 1.0,
    ) -> None:
        self._url = url.rstrip("/")
        self._index_name = index_name
        self._timeout_seconds = timeout_seconds
        self._retry_attempts = retry_attempts
        self._limit = limit
        self._min_score = min_score

    async def retrieve(self, case: CaseRecord) -> list[Evidence]:
        if not self._url or not self._index_name:
            return []

        query_text = build_case_query(case)
        endpoint = f"{self._url}/{quote(self._index_name)}/_search"
        filters: list[dict[str, object]] = []
        if case.issue_type:
            filters.append({"term": {"issue_type": case.issue_type}})
        if case.customer_tier:
            filters.append({"term": {"tags": case.customer_tier.lower()}})

        bool_query: dict[str, object] = {
            "must": [
                {
                    "multi_match": {
                        "query": query_text,
                        "fields": ["title^3", "excerpt^2", "text", "source", "issue_type"],
                        "type": "best_fields",
                    }
                }
            ],
        }
        if filters:
            bool_query["filter"] = filters

        payload = {
            "size": self._limit,
            "min_score": self._min_score,
            "query": {"bool": bool_query},
        }

        async def _request() -> httpx.Response:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(endpoint, json=payload)
                response.raise_for_status()
                return response

        try:
            response = await retry_async(
                _request,
                attempts=self._retry_attempts,
                retry_exceptions=(httpx.HTTPError,),
                on_retry=lambda attempt, exc: logger.warning(
                    "opensearch_retry",
                    attempt=attempt,
                    error=str(exc),
                    index=self._index_name,
                ),
            )
        except httpx.HTTPError as exc:
            logger.warning("opensearch_retrieval_failed", error=str(exc), index=self._index_name)
            return []

        body_obj: object = response.json()
        body = cast("dict[str, object]", body_obj) if isinstance(body_obj, dict) else {}
        hits = _list_field(_dict_field(body, "hits"), "hits")
        return [
            evidence
            for evidence in (_evidence_from_hit(hit) for hit in hits)
            if evidence is not None
        ]


class QdrantRetriever:
    """Retrieve evidence payloads from a local Qdrant collection.

    This adapter keeps the first integration simple: it scrolls recent payloads
    and ranks them locally by case keywords. Vector embedding can replace the
    local scorer once the embedding provider and schema are finalized.
    """

    def __init__(
        self,
        *,
        url: str,
        collection_name: str,
        timeout_seconds: float,
        retry_attempts: int,
        limit: int = 20,
        result_limit: int = 5,
    ) -> None:
        self._url = url.rstrip("/")
        self._collection_name = collection_name
        self._timeout_seconds = timeout_seconds
        self._retry_attempts = retry_attempts
        self._limit = limit
        self._result_limit = result_limit

    async def retrieve(self, case: CaseRecord) -> list[Evidence]:
        if not self._url or not self._collection_name:
            return []

        endpoint = f"{self._url}/collections/{quote(self._collection_name)}/points/scroll"
        must_conditions: list[dict[str, object]] = []
        if case.issue_type:
            must_conditions.append({"key": "issue_type", "match": {"value": case.issue_type}})
        payload: dict[str, object] = {
            "limit": self._limit,
            "with_payload": True,
            "with_vector": False,
        }
        if must_conditions:
            payload["filter"] = {"must": must_conditions}

        async def _request() -> httpx.Response:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(endpoint, json=payload)
                response.raise_for_status()
                return response

        try:
            response = await retry_async(
                _request,
                attempts=self._retry_attempts,
                retry_exceptions=(httpx.HTTPError,),
                on_retry=lambda attempt, exc: logger.warning(
                    "qdrant_retry",
                    attempt=attempt,
                    error=str(exc),
                    collection=self._collection_name,
                ),
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "qdrant_retrieval_failed",
                error=str(exc),
                collection=self._collection_name,
            )
            return []

        body_obj: object = response.json()
        body = cast("dict[str, object]", body_obj) if isinstance(body_obj, dict) else {}
        points = _list_field(_dict_field(body, "result"), "points")
        evidence = [
            item
            for item in (
                _evidence_from_payload(_point_payload(point), score=1.0) for point in points
            )
            if item is not None
        ]
        return rank_evidence(case, evidence)[: self._result_limit]


class HybridEvidenceRetriever:
    """Query configured external retrievers and merge unique evidence."""

    def __init__(
        self,
        retrievers: Sequence[EvidenceRetriever],
        *,
        fallback: EvidenceRetriever | None = None,
    ) -> None:
        self._retrievers = list(retrievers)
        self._fallback = fallback

    async def retrieve(self, case: CaseRecord) -> list[Evidence]:
        evidence: list[Evidence] = []
        seen_sources: set[str] = set()
        results = await asyncio.gather(
            *(retriever.retrieve(case) for retriever in self._retrievers),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, BaseException):
                logger.warning("hybrid_retriever_failed", error=str(result))
                continue
            for item in result:
                if item.source not in seen_sources:
                    evidence.append(item)
                    seen_sources.add(item.source)

        if evidence or self._fallback is None:
            return evidence
        return await self._fallback.retrieve(case)


class NullEvidenceRetriever:
    """No-op retriever when RAG is disabled."""

    async def retrieve(self, case: CaseRecord) -> list[Evidence]:
        return []


def build_retriever(settings: Settings) -> EvidenceRetriever:
    backend = settings.rag_backend.lower().strip()

    if backend in {"none", "off", ""}:
        return NullEvidenceRetriever()

    opensearch = OpenSearchRetriever(
        url=settings.opensearch_url,
        index_name=settings.opensearch_index,
        timeout_seconds=settings.retrieval_timeout_seconds,
        retry_attempts=settings.integration_retry_attempts,
        min_score=settings.evidence_min_relevance_score,
    )
    qdrant = QdrantRetriever(
        url=settings.qdrant_url,
        collection_name=settings.qdrant_collection,
        timeout_seconds=settings.retrieval_timeout_seconds,
        retry_attempts=settings.integration_retry_attempts,
    )

    if backend == "opensearch":
        return HybridEvidenceRetriever([opensearch])
    if backend == "qdrant":
        return HybridEvidenceRetriever([qdrant])
    if backend == "hybrid":
        return HybridEvidenceRetriever([opensearch, qdrant])
    raise ValueError(
        f"Unsupported RAG_BACKEND={backend!r}. "
        "Use opensearch, qdrant, hybrid, or none."
    )


def build_case_query(case: CaseRecord) -> str:
    return " ".join(
        part
        for part in [
            case.issue_type,
            case.summary,
            case.requested_outcome,
            case.customer_tier,
            " ".join(case.recent_messages[-3:]),
        ]
        if part
    )


def rank_evidence(case: CaseRecord, evidence: list[Evidence]) -> list[Evidence]:
    terms = {
        term.lower()
        for term in build_case_query(case).replace("_", " ").split()
        if len(term) >= MIN_QUERY_TERM_LENGTH
    }

    def score(item: Evidence) -> int:
        text = f"{item.title} {item.excerpt} {item.source}".lower()
        keyword_score = sum(1 for term in terms if term in text)
        return keyword_score + int(item.relevance_score)

    return sorted(evidence, key=score, reverse=True)


def _hit_source(hit: object) -> dict[str, object]:
    if not isinstance(hit, dict):
        return {}
    hit_map = cast("dict[str, object]", hit)
    source: object = hit_map.get("_source", {})
    return cast("dict[str, object]", source) if isinstance(source, dict) else {}


def _point_payload(point: object) -> dict[str, object]:
    if not isinstance(point, dict):
        return {}
    point_map = cast("dict[str, object]", point)
    payload: object = point_map.get("payload", {})
    return cast("dict[str, object]", payload) if isinstance(payload, dict) else {}


def _dict_field(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    return cast("dict[str, object]", value) if isinstance(value, dict) else {}


def _list_field(payload: dict[str, object], key: str) -> list[object]:
    value = payload.get(key)
    return cast("list[object]", value) if isinstance(value, list) else []


def _evidence_from_hit(hit: object) -> Evidence | None:
    if not isinstance(hit, dict):
        return None
    hit_map = cast("dict[str, object]", hit)
    score_value = hit_map.get("_score", 0.0)
    score = float(score_value) if isinstance(score_value, int | float) else 0.0
    return _evidence_from_payload(_hit_source(hit), score=score)


def _evidence_from_payload(payload: dict[str, object], *, score: float = 0.0) -> Evidence | None:
    if not payload:
        return None

    source = _string_field(payload, "source") or _string_field(payload, "id")
    title = _string_field(payload, "title")
    excerpt = (
        _string_field(payload, "excerpt")
        or _string_field(payload, "text")
        or _string_field(payload, "body")
    )
    if not title or not excerpt:
        return None
    raw_tags: object = payload.get("tags", [])
    tag_values = cast("list[object]", raw_tags) if isinstance(raw_tags, list) else []
    tags = [tag for tag in tag_values if isinstance(tag, str)]
    issue_type = _string_field(payload, "issue_type")
    indexed_at = _string_field(payload, "indexed_at") or None
    return Evidence(
        source=source or f"rag://{title}",
        title=title,
        excerpt=excerpt,
        tags=tags,
        issue_type=issue_type,
        relevance_score=score,
        indexed_at=indexed_at,
    )


def _string_field(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""
