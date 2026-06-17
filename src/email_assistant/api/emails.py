"""Email generation API endpoints."""

from __future__ import annotations

from typing import cast

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from case_assistant_api.agents.emails.graph import EmailGenerationAgent

logger = structlog.get_logger()
router = APIRouter(prefix="/emails", tags=["emails"])


class GenerateEmailRequest(BaseModel):
    """Request to generate an email."""

    intent: str = Field(
        ...,
        description="The core purpose of the email (e.g., 'Follow up after meeting')",
        min_length=1,
        max_length=500,
    )
    key_facts: list[str] = Field(
        ...,
        description="Bullet points of information to include in the email",
        min_length=1,
    )
    tone: str = Field(
        ...,
        description="The desired style (e.g., formal, casual, urgent, empathetic)",
        min_length=1,
        max_length=100,
    )


class GenerateEmailResponse(BaseModel):
    """Response containing the generated email."""

    subject: str = Field(..., description="Generated email subject line")
    body: str = Field(..., description="Generated email body")
    intent: str = Field(..., description="The input intent")
    tone: str = Field(..., description="The input tone")
    key_facts_used: list[str] = Field(..., description="Key facts incorporated into the email")


@router.post("/generate", response_model=GenerateEmailResponse)
async def generate_email(request: GenerateEmailRequest) -> GenerateEmailResponse:
    """Generate a professional email based on intent, key facts, and tone."""
    agent = EmailGenerationAgent()
    try:
        result = await agent.generate(
            intent=request.intent,
            key_facts=request.key_facts,
            tone=request.tone,
        )
        return GenerateEmailResponse(
            subject=result.subject,
            body=result.body,
            intent=request.intent,
            tone=request.tone,
            key_facts_used=request.key_facts,
        )
    except Exception as exc:
        logger.error("email_generation_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Email generation failed: {exc}") from exc
