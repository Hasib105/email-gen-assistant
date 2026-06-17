"""FastAPI app — Email Generation Assistant with LangGraph guardrails."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from email_assistant.agents.pipeline import generate_with_guardrails
from email_assistant.config import get_settings

app = FastAPI(title="Email Generation Assistant", version="0.1.0")


class EmailRequest(BaseModel):
    intent: str
    key_facts: list[str]
    tone: str


class EmailResponse(BaseModel):
    subject: str
    body: str
    model: str
    strategy: str
    tone_score: float
    fact_score: float
    clarity_score: float
    warnings: list[str]
    passed: bool
    retries: int


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/generate", response_model=EmailResponse)
def generate_email(req: EmailRequest) -> EmailResponse:
    settings = get_settings()
    result = generate_with_guardrails(
        intent=req.intent,
        key_facts=req.key_facts,
        tone=req.tone,
        model=settings.nvidia_model_a,
        strategy="advanced",
    )
    return EmailResponse(
        subject=result["subject"],
        body=result["body"],
        model=settings.nvidia_model_a,
        strategy="advanced",
        tone_score=result["tone_score"],
        fact_score=result["fact_score"],
        clarity_score=result["clarity_score"],
        warnings=result["warnings"],
        passed=result["passed"],
        retries=result["retries"],
    )
