"""Email generation agent components."""

from __future__ import annotations

from case_assistant_api.agents.emails.graph import EmailGenerationAgent
from case_assistant_api.agents.emails.prompts import build_email_generation_prompt
from case_assistant_api.agents.emails.schema import EmailDraft

__all__ = [
    "EmailDraft",
    "EmailGenerationAgent",
    "build_email_generation_prompt",
]
