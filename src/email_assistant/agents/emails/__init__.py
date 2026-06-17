"""Email generation agent components."""

from __future__ import annotations

from email_assistant.agents.emails.graph import EmailGenerationAgent
from email_assistant.agents.emails.prompts import build_email_generation_prompt
from email_assistant.agents.emails.schema import EmailDraft

__all__ = [
    "EmailDraft",
    "EmailGenerationAgent",
    "build_email_generation_prompt",
]
