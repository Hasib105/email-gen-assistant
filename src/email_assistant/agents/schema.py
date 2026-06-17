"""Pydantic schema for structured email output."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EmailDraft(BaseModel):
    subject: str = Field(..., description="The email subject line")
    body: str = Field(..., description="The email body text")
