"""Job status and payload schemas for durable background work."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def utc_now() -> datetime:
    return datetime.now(UTC)


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class JobType(StrEnum):
    GENERATE_DRAFT = "generate_draft"
    EDIT_DRAFT = "edit_draft"


@dataclass(frozen=True)
class EmailJobPayload:
    """Payload for email generation jobs."""

    case_id: str
    user_id: str = ""
    intent: str = ""
    key_facts: str = ""
    tone: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "case_id": self.case_id,
            "user_id": self.user_id,
            "intent": self.intent,
            "key_facts": self.key_facts,
            "tone": self.tone,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EmailJobPayload:
        return cls(
            case_id=str(data.get("case_id", "")),
            user_id=str(data.get("user_id", "")),
            intent=str(data.get("intent", "")),
            key_facts=str(data.get("key_facts", "")),
            tone=str(data.get("tone", "")),
        )


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    job_type: JobType
    status: JobStatus
    case_id: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int
    error: str = ""
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
