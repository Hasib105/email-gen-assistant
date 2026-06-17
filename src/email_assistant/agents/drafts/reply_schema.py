"""Structured output schema for the LLM draft-reply node.

LangChain's ``with_structured_output()`` passes this Pydantic model to the LLM
as a function-call tool, so the model is constrained to populate every field
rather than generating free-form text.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CaseDraftReply(BaseModel):
    """Structured reply produced by the LLM for a support case."""

    subject: str = Field(
        description=(
            "Short, professional email subject line. "
            "Reference the issue type but never use raw personal data — "
            "use masked placeholders such as CUSTOMER_1 or BOOKING_REF_1."
        )
    )
    body: str = Field(
        description=(
            "Full email body in a professional, empathetic tone. "
            "Begin with a greeting. Use masked placeholders only (e.g. CUSTOMER_1). "
            "Include next steps, relevant policy points, and a closing line. "
            "Do NOT reveal any raw PII."
        )
    )
    recommended_actions: list[str] = Field(
        default_factory=list,
        description=(
            "Up to 3 concrete internal action items for the support agent to complete next. "
            "These are NEVER shown to the customer. "
            "Examples: 'Check same-day ANA/JAL availability CTS to HND', "
            "'Verify hotel voucher eligibility for weather disruption'."
        ),
    )
