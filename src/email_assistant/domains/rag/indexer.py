"""Store evidence documents in local search backends."""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote
from uuid import NAMESPACE_URL, uuid5

import httpx
import structlog
from email_assistant.config import Settings
from email_assistant.domains.rag.retriever import Evidence
from email_assistant.resilience import retry_async

logger = structlog.get_logger()


@dataclass(frozen=True)
class EvidenceIndexResult:
    backend: str
    stored_count: int
    ok: bool
    detail: str = ""


class EvidenceIndexService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def index_evidence(self, evidence: list[Evidence]) -> list[EvidenceIndexResult]:
        results: list[EvidenceIndexResult] = []
        backend = self._settings.rag_backend.lower().strip()

        if backend in {"opensearch", "hybrid"}:
            results.append(await self._index_opensearch(evidence))
        if backend in {"qdrant", "hybrid"}:
            results.append(await self._index_qdrant(evidence))
        if backend == "static":
            results.append(
                EvidenceIndexResult(
                    backend="static",
                    stored_count=0,
                    ok=False,
                    detail=(
                        "Static backend is disabled. Set RAG_BACKEND to opensearch, "
                        "qdrant, or hybrid and run scripts/seed.py."
                    ),
                )
            )

        logger.info(
            "evidence_index_complete",
            backend=backend,
            stored_count=sum(result.stored_count for result in results),
        )
        return results

    async def _index_opensearch(self, evidence: list[Evidence]) -> EvidenceIndexResult:
        if not self._settings.opensearch_url or not self._settings.opensearch_index:
            return EvidenceIndexResult("opensearch", 0, False, "OpenSearch is not configured.")

        base_url = self._settings.opensearch_url.rstrip("/")
        index_name = quote(self._settings.opensearch_index)
        index_url = f"{base_url}/{index_name}"
        timeout = self._settings.retrieval_timeout_seconds

        async def _request() -> None:
            async with httpx.AsyncClient(timeout=timeout) as client:
                await _raise_after_request(
                    client.put(
                        index_url,
                        json={
                            "mappings": {
                                "properties": {
                                    "source": {"type": "keyword"},
                                    "title": {"type": "text"},
                                    "excerpt": {"type": "text"},
                                    "text": {"type": "text"},
                                    "tags": {"type": "keyword"},
                                    "issue_type": {"type": "keyword"},
                                    "indexed_at": {"type": "date"},
                                    "version": {"type": "integer"},
                                }
                            }
                        },
                    ),
                    allow_statuses={400},
                )
                for item in evidence:
                    doc_id = quote(_document_id(item.source))
                    await _raise_after_request(
                        client.put(f"{index_url}/_doc/{doc_id}", json=_payload(item))
                    )

        try:
            await retry_async(
                _request,
                attempts=self._settings.integration_retry_attempts,
                retry_exceptions=(httpx.HTTPError,),
            )
        except httpx.HTTPError as exc:
            return EvidenceIndexResult("opensearch", 0, False, str(exc))
        return EvidenceIndexResult("opensearch", len(evidence), True)

    async def _index_qdrant(self, evidence: list[Evidence]) -> EvidenceIndexResult:
        if not self._settings.qdrant_url or not self._settings.qdrant_collection:
            return EvidenceIndexResult("qdrant", 0, False, "Qdrant is not configured.")

        base_url = self._settings.qdrant_url.rstrip("/")
        collection = quote(self._settings.qdrant_collection)
        collection_url = f"{base_url}/collections/{collection}"
        timeout = self._settings.retrieval_timeout_seconds

        async def _request() -> None:
            async with httpx.AsyncClient(timeout=timeout) as client:
                await _raise_after_request(
                    client.put(
                        collection_url,
                        json={"vectors": {"size": 1, "distance": "Cosine"}},
                    ),
                    allow_statuses={409},
                )
                await _raise_after_request(
                    client.put(
                        f"{collection_url}/points",
                        json={
                            "points": [
                                {
                                    "id": _point_id(item.source),
                                    "vector": [0.0],
                                    "payload": _payload(item),
                                }
                                for item in evidence
                            ]
                        },
                    )
                )

        try:
            await retry_async(
                _request,
                attempts=self._settings.integration_retry_attempts,
                retry_exceptions=(httpx.HTTPError,),
            )
        except httpx.HTTPError as exc:
            return EvidenceIndexResult("qdrant", 0, False, str(exc))
        return EvidenceIndexResult("qdrant", len(evidence), True)


async def _raise_after_request(
    response_awaitable: Awaitable[httpx.Response],
    *,
    allow_statuses: set[int] | None = None,
) -> None:
    response = await response_awaitable
    if allow_statuses and response.status_code in allow_statuses:
        return
    response.raise_for_status()


def _payload(evidence: Evidence) -> dict[str, object]:
    issue_type = next((tag for tag in evidence.tags if tag not in {"sop", "support"}), "")
    indexed_at = datetime.now(UTC).isoformat()
    return {
        "source": evidence.source,
        "title": evidence.title,
        "excerpt": evidence.excerpt,
        "text": f"{evidence.title}\n{evidence.excerpt}",
        "tags": evidence.tags,
        "issue_type": issue_type,
        "indexed_at": indexed_at,
        "version": 1,
    }


def _document_id(source: str) -> str:
    return str(uuid5(NAMESPACE_URL, source))


def _point_id(source: str) -> str:
    return str(uuid5(NAMESPACE_URL, source))
