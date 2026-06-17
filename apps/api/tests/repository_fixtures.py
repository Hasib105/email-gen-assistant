"""Test-only repositories backed by the development seed script."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from case_assistant_api.domains.cases.schemas import CaseNotFoundError, CaseRecord
from case_assistant_api.domains.rag.retriever import Evidence


def _seed_module() -> object:
    path = Path(__file__).resolve().parents[3] / "scripts" / "seed.py"
    spec = importlib.util.spec_from_file_location("dev_seed", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load seed module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SeedCaseRepository:
    """Load demo cases from scripts/seed.py for unit tests only."""

    def __init__(self) -> None:
        seed = _seed_module()
        self._cases = seed.dev_cases()

    async def setup(self) -> None:
        return None

    async def get_case(self, case_id: str) -> CaseRecord:
        normalized = case_id.strip().upper()
        record = self._cases.get(normalized)
        if record is None:
            raise CaseNotFoundError(case_id=normalized)
        return record


class SeedEvidenceRetriever:
    """Return seeded SOP evidence for unit tests only."""

    async def retrieve(self, case: CaseRecord) -> list[Evidence]:
        seed = _seed_module()
        catalog = seed.dev_evidence()
        if case.issue_type == "flight_disruption":
            items = [
                item
                for item in catalog
                if "flight_disruption" in item.tags or case.customer_tier.lower() in item.tags
            ]
            return [item.model_copy(update={"relevance_score": 3.0}) for item in items]
        items = [item for item in catalog if "general" in item.tags]
        return [item.model_copy(update={"relevance_score": 2.0}) for item in items]
