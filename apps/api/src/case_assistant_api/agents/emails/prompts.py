"""Advanced prompt templates for email generation.

Uses a combination of three advanced prompting techniques:
1. Role-Playing: The LLM acts as a professional email writing expert
2. Chain-of-Thought: Step-by-step reasoning before writing
3. Few-Shot Examples: High-quality reference emails for different tones
"""

from __future__ import annotations

# Role-playing system prompt that establishes expertise
SYSTEM_ROLE = """You are a world-class professional email writer with 15 years of experience
in corporate communications. You craft emails that are clear, persuasive, and perfectly
tailored to the requested tone. Your emails always have a compelling subject line and
well-structured body that achieves the stated intent."""

# Chain-of-Thought instruction for reasoning before writing
CHAIN_OF_THOUGHT_INSTRUCTION = """Before writing the email, think through these steps:
1. UNDERSTAND the intent: What is the primary goal of this email?
2. ORGANIZE the facts: Which key facts are most relevant and in what order?
3. MATCH the tone: How should the language, sentence structure, and word choice reflect the requested tone?
4. CRAFT the subject: What subject line will grab attention and reflect the email's purpose?
5. WRITE the body: Compose a well-structured email that flows naturally and achieves the intent.

Then provide your final output as a structured EmailDraft with subject and body."""

# Few-shot examples for different tones
FEW_SHOT_EXAMPLES = """
## Example 1: Formal Tone
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

## Example 2: Casual Tone
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

## Example 3: Urgent Tone
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

## Example 4: Empathetic Tone
Intent: Respond to customer complaint about delayed shipment
Key Facts: Order was delayed by 2 weeks, refund processing, improved logistics in place
Tone: Empathetic

Subject: We're Sorry — Your Order Update
Body: Dear [Customer],

I completely understand your frustration with the delay in receiving your order. Waiting two weeks beyond the promised delivery date is unacceptable, and I sincerely apologize for the inconvenience this has caused you.

Your refund has been processed and you should see it reflected in your account within 3-5 business days. Additionally, we have implemented improved logistics measures to prevent similar delays in the future.

Your experience matters deeply to us, and we are committed to doing better. Please do not hesitate to reach out if there is anything else I can help you with.

With sincere apologies,
[Your Name]
"""


def build_email_generation_prompt(
    *,
    intent: str,
    key_facts: list[str],
    tone: str,
) -> str:
    """Build the full prompt using Role-Playing + Chain-of-Thought + Few-Shot prompting.

    This advanced prompt engineering technique combines:
    1. Role-Playing: Establishes the LLM as an expert email writer
    2. Chain-of-Thought: Guides step-by-step reasoning before writing
    3. Few-Shot Examples: Provides high-quality reference outputs for different tones
    """
    facts_block = "\n".join(f"- {fact}" for fact in key_facts)

    return f"""{SYSTEM_ROLE}

{CHAIN_OF_THOUGHT_INSTRUCTION}

{FEW_SHOT_EXAMPLES}

---

## Now write an email for the following request:

Intent: {intent}

Key Facts:
{facts_block}

Tone: {tone}

Think through the steps above, then provide your EmailDraft with subject and body."""
