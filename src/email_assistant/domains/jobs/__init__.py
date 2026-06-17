"""Durable background job persistence."""

from email_assistant.domains.jobs.schemas import (
    EmailJobPayload,
    JobRecord,
    JobStatus,
    JobType,
)
from email_assistant.domains.jobs.store import get_job_store

__all__ = [
    "EmailJobPayload",
    "JobRecord",
    "JobStatus",
    "JobType",
    "get_job_store",
]
