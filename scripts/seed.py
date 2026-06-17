"""Seed local database and search stores (run manually after Docker is up).

Usage:
    uv run python scripts/seed.py

Empty databases before the first run are normal.
"""

from __future__ import annotations

import asyncio

import orjson
import structlog
from email_assistant.config import get_settings
from email_assistant.db.migrations import run_migrations
from email_assistant.db.pool import close_pool, get_connection, is_sqlite_mode, open_pool
from email_assistant.domains.cases.repository import validate_identifier
from email_assistant.domains.cases.schemas import CaseRecord
from email_assistant.domains.rag.indexer import EvidenceIndexService
from email_assistant.domains.rag.retriever import Evidence

logger = structlog.get_logger()


def dev_cases() -> dict[str, CaseRecord]:
    raw: dict[str, object] = {
        "CASE-1001": {
            "case_id": "CASE-1001",
            "customer_name": "Alex Johnson",
            "customer_email": "alex.johnson@example.com",
            "customer_phone": "+1 555-123-4567",
            "customer_tier": "Gold",
            "booking_reference": "BK-789012",
            "issue_type": "flight_disruption",
            "summary": "Return flight from NYC to LAX was cancelled due to severe weather. Customer is stranded in New York.",
            "requested_outcome": "Find same-day rebooking to Los Angeles and explain hotel voucher eligibility if overnight stay is needed.",
            "itinerary": [
                {
                    "origin": "JFK",
                    "destination": "LAX",
                    "flight_number": "AA1234",
                    "departure_date": "2026-06-10",
                    "status": "cancelled",
                }
            ],
            "recent_messages": [
                "Customer says they can accept a late flight if it arrives in LA before midnight.",
                "Customer asked whether a hotel voucher applies if no same-day option exists.",
                "Customer mentioned an important meeting in downtown LA tomorrow morning.",
            ],
            "travel_preferences": {
                "preferred_seat": "window",
                "meal_preference": "vegetarian",
                "frequent_flyer_number": "AA-GOLD-882211",
                "preferred_airlines": ["American Airlines", "Delta"],
                "preferred_hotel_chain": "Marriott",
                "notes": "Prefers morning departures. Always requests extra legroom when available.",
            },
            "travel_history": [
                {
                    "trip_id": "T-0091",
                    "origin": "LAX",
                    "destination": "JFK",
                    "date": "2025-11-15",
                    "status": "completed",
                    "notes": "Business trip to New York; upgraded to first class as Gold benefit",
                },
                {
                    "trip_id": "T-0085",
                    "origin": "LAX",
                    "destination": "SFO",
                    "date": "2025-08-22",
                    "status": "completed",
                    "notes": "Leisure trip to San Francisco, no issues reported",
                },
            ],
        }
    }
    return {key: CaseRecord.model_validate(value) for key, value in raw.items()}


def dev_evidence() -> list[Evidence]:
    raw: list[object] = [
        {
            "source": "sop://flight-disruption/rebooking",
            "title": "Same-day disruption rebooking",
            "excerpt": "Offer same-day alternatives first. If arrival is delayed overnight, explain hotel voucher eligibility according to fare and disruption reason.",
            "tags": ["flight_disruption", "rebooking", "sop"],
        },
        {
            "source": "sop://customer-tier/gold",
            "title": "Gold tier support handling",
            "excerpt": "Gold customers should receive proactive next-step language and a concise summary of available options before asking them to choose.",
            "tags": ["gold", "customer_tier", "sop"],
        },
        {
            "source": "sop://general/support-draft",
            "title": "General support draft",
            "excerpt": "Acknowledge the request, state what is known, and give a reviewable next step.",
            "tags": ["general", "support", "sop"],
        },
    ]
    return [Evidence.model_validate(item) for item in raw if isinstance(item, dict)]


async def seed_database() -> int:
    settings = get_settings()
    table_name = validate_identifier(settings.case_table_name)
    cases = dev_cases()
    await open_pool(settings)
    try:
        await run_migrations()
        async with get_connection() as connection:
            for case_id, record in cases.items():
                payload_json = orjson.dumps(record.model_dump()).decode()
                if is_sqlite_mode():
                    await connection.execute(
                        f"""
                        INSERT INTO {table_name}
                            (case_id, issue_type, customer_tier, payload, created_at, updated_at)
                        VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
                        ON CONFLICT (case_id) DO UPDATE SET
                            issue_type = excluded.issue_type,
                            customer_tier = excluded.customer_tier,
                            payload = excluded.payload,
                            updated_at = datetime('now')
                        """,
                        case_id,
                        record.issue_type,
                        record.customer_tier,
                        payload_json,
                    )
                else:
                    await connection.execute(
                        f"""
                        INSERT INTO {table_name}
                            (case_id, issue_type, customer_tier, payload, created_at, updated_at)
                        VALUES ($1, $2, $3, $4::jsonb, now(), now())
                        ON CONFLICT (case_id) DO UPDATE
                        SET issue_type = EXCLUDED.issue_type,
                            customer_tier = EXCLUDED.customer_tier,
                            payload = EXCLUDED.payload,
                            updated_at = now()
                        """,
                        case_id,
                        record.issue_type,
                        record.customer_tier,
                        payload_json,
                    )
    finally:
        await close_pool()
    logger.info("database_seed_complete", case_count=len(cases))
    return len(cases)


async def seed_search() -> int:
    settings = get_settings()
    if settings.rag_backend.lower() in {"none", "off", ""}:
        print("RAG_BACKEND is none — skipping search store seeding.")
        return 0
    results = await EvidenceIndexService(settings).index_evidence(dev_evidence())
    exit_code = 0
    for result in results:
        status = "ok" if result.ok else "failed"
        detail = f" ({result.detail})" if result.detail else ""
        print(f"{result.backend}: {status}, stored={result.stored_count}{detail}")
        if not result.ok:
            exit_code = 1
    return exit_code


async def main() -> int:
    case_count = await seed_database()
    db_type = "SQLite" if is_sqlite_mode() else "PostgreSQL"
    print(f"Seeded {case_count} cases into {db_type}.")
    return await seed_search()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
