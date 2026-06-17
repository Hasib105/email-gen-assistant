"""Email generation agent — prompt templates + ChatNVIDIA LLM call."""

from __future__ import annotations

import time
from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from email_assistant.agents.llm import get_llm
from email_assistant.agents.schema import EmailDraft
from email_assistant.config import Settings, get_settings


# ── Advanced Prompt (Strategy A) ────────────────────────────────────────────

SYSTEM_ROLE = """You are a world-class professional email writer with 15 years of experience
in corporate communications. You craft emails that are clear, persuasive, and perfectly
tailored to the requested tone. Your emails always have a compelling subject line and
well-structured body that achieves the stated intent."""

CHAIN_OF_THOUGHT = """Before writing the email, think through these steps:
1. UNDERSTAND the intent: What is the primary goal of this email?
2. ORGANIZE the facts: Which key facts are most relevant and in what order?
3. MATCH the tone: How should the language, sentence structure, and word choice reflect the requested tone?
4. CRAFT the subject: What subject line will grab attention and reflect the email's purpose?
5. WRITE the body: Compose a well-structured email that flows naturally and achieves the intent.

Output ONLY the final email with Subject and Body. No explanations."""

FEW_SHOT = """
EXAMPLE 1 — Formal:
Intent: Request budget approval for Q3 marketing campaign
Key Facts: Campaign budget is $50,000, Expected ROI is 3x, Targets 10,000 new leads
Tone: Formal

Subject: Budget Approval Request — Q3 Marketing Campaign
Body: Dear [Recipient],

I am writing to request your approval for the Q3 marketing campaign budget allocation.

The proposed campaign requires an investment of $50,000, with a projected return on investment of 3x within the quarter. Our analysis indicates this initiative will generate approximately 10,000 new qualified leads, significantly expanding our customer pipeline.

I have attached the detailed campaign plan and financial projections for your review. I am available to discuss this further at your earliest convenience.

Thank you for your consideration.

Best regards,
[Your Name]

---

EXAMPLE 2 — Casual:
Intent: Invite colleague to team lunch
Key Facts: New Italian restaurant downtown, Friday at noon, celebrating project completion
Tone: Casual

Subject: Team lunch this Friday?
Body: Hey!

Just wanted to check — there's a new Italian place downtown that looks amazing. Want to grab lunch there this Friday around noon? We've been crushing it on the project lately and it'd be great to celebrate.

Let me know if you're in!

Cheers,
[Your Name]

---

EXAMPLE 3 — Urgent:
Intent: Notify team of critical production issue
Key Facts: Payment service is down, affecting 30% of transactions, need all hands on deck
Tone: Urgent

Subject: URGENT: Payment Service Outage — Immediate Action Required
Body: Team,

We are currently experiencing a critical outage in our payment service that is impacting approximately 30% of all transactions. This requires immediate attention from all available engineers.

Please join the incident bridge call at once and prioritize this issue above all other tasks. I will provide updates every 15 minutes until resolution.

This is our top priority.

[Your Name]

---

EXAMPLE 4 — Empathetic:
Intent: Respond to customer complaint about delayed shipment
Key Facts: Order was delayed by 2 weeks, refund processing, improved logistics in place
Tone: Empathetic

Subject: We're Sorry — Your Order Update
Body: Dear [Customer],

I completely understand your frustration with the delay in receiving your order. Waiting two weeks beyond the promised delivery date is unacceptable, and I sincerely apologize for the inconvenience this has caused you.

Your refund has been processed and you should see it reflected in your account within 3-5 business days. Additionally, we have implemented improved logistics measures to prevent similar delays in the future.

Your experience matters deeply to us.

With sincere apologies,
[Your Name]
"""


def build_advanced_prompt(*, intent: str, key_facts: list[str], tone: str) -> str:
    facts_block = "\n".join(f"- {f}" for f in key_facts)
    return f"""{SYSTEM_ROLE}

{CHAIN_OF_THOUGHT}

{FEW_SHOT}

---

NOW WRITE THIS EMAIL:
Intent: {intent}
Key Facts:
{facts_block}
Tone: {tone}

Email:"""


# ── Naive Prompt (Strategy B — baseline) ─────────────────────────────────────

def build_naive_prompt(*, intent: str, key_facts: list[str], tone: str) -> str:
    facts_block = ", ".join(key_facts)
    return f"""Write an email.
Intent: {intent}
Facts: {facts_block}
Tone: {tone}"""


# ── Generation ───────────────────────────────────────────────────────────────

def generate(
    *,
    intent: str,
    key_facts: list[str],
    tone: str,
    model: str,
    strategy: str = "advanced",
    settings: Settings | None = None,
) -> tuple[str, str, float]:
    """Generate email via ChatNVIDIA. Returns (subject, body, elapsed_seconds)."""
    cfg = settings or get_settings()
    if strategy == "naive":
        prompt = build_naive_prompt(intent=intent, key_facts=key_facts, tone=tone)
    else:
        prompt = build_advanced_prompt(intent=intent, key_facts=key_facts, tone=tone)

    llm = get_llm(model=model, settings=cfg)
    structured_llm = llm.with_structured_output(EmailDraft)

    start = time.time()
    result = structured_llm.invoke([HumanMessage(content=prompt)])
    elapsed = time.time() - start

    result = cast("EmailDraft", result)
    return result.subject, result.body, elapsed
