"""LangGraph pipeline for email generation with tone and fact guardrails.

Flow:
  generate_email → validate_tone → validate_facts → finalize
       ↑                ↓ (fail)        ↓ (fail)
       └────────────────┘               └────────┘
       (regenerate with feedback, max 2 retries)
"""

from __future__ import annotations

from typing import NotRequired, TypedDict, cast

from langgraph.graph import END, START, StateGraph

from email_assistant.agents.emails import (
    build_advanced_prompt,
    build_naive_prompt,
)
from email_assistant.agents.llm import get_llm
from email_assistant.agents.schema import EmailDraft
from email_assistant.config import get_settings
from email_assistant.evaluation.metrics import (
    ClarityConcisenessMetric,
    FactRecallMetric,
    ToneAlignmentMetric,
)

# ── State ────────────────────────────────────────────────────────────────────


class EmailState(TypedDict):
    # Input (always present)
    intent: str
    key_facts: list[str]
    tone: str
    model: str
    strategy: str  # "advanced" or "naive"

    # Intermediate
    retry_count: NotRequired[int]
    tone_feedback: NotRequired[str]
    fact_feedback: NotRequired[str]

    # Output
    subject: NotRequired[str]
    body: NotRequired[str]
    tone_score: NotRequired[float]
    fact_score: NotRequired[float]
    clarity_score: NotRequired[float]
    warnings: NotRequired[list[str]]
    passed: NotRequired[bool]


MAX_RETRIES = 2


# ── Nodes ────────────────────────────────────────────────────────────────────

def generate_email(state: EmailState) -> dict:
    """Call LLM to generate email."""
    settings = get_settings()
    llm = get_llm(model=state["model"], settings=settings)
    structured_llm = llm.with_structured_output(EmailDraft)

    # Build prompt with feedback from previous failed attempts
    tone_fb = state.get("tone_feedback", "")
    fact_fb = state.get("fact_feedback", "")
    extra = ""
    if tone_fb:
        extra += f"\nTONE FEEDBACK: {tone_fb}"
    if fact_fb:
        extra += f"\nFACT FEEDBACK: {fact_fb}"

    if state.get("strategy") == "naive":
        prompt = build_naive_prompt(
            intent=state["intent"], key_facts=state["key_facts"], tone=state["tone"]
        )
    else:
        prompt = build_advanced_prompt(
            intent=state["intent"], key_facts=state["key_facts"], tone=state["tone"]
        )

    if extra:
        prompt += f"\n\nIMPORTANT FIXES FOR NEXT ATTEMPT:{extra}"

    result = cast("EmailDraft", structured_llm.invoke(prompt))

    return {
        "subject": result.subject,
        "body": result.body,
        "retry_count": state.get("retry_count", 0) + 1,
    }


def validate_tone(state: EmailState) -> dict:
    """Check tone alignment. Return score and feedback if failing."""
    metric = ToneAlignmentMetric()
    body = state.get("body", "")
    result = metric.evaluate(state["tone"], body)

    if result.score >= 0.5:
        return {"tone_score": result.score, "tone_feedback": ""}

    # Build feedback for regeneration
    feedback = f"Email tone does not match '{state['tone']}'. "
    if "Contradictions" in result.details:
        feedback += "Remove contradicting language. "
    feedback += f"Use more {state['tone']}-appropriate words and sentence structure."
    return {"tone_score": result.score, "tone_feedback": feedback}


def validate_facts(state: EmailState) -> dict:
    """Check fact recall. Return score and feedback if failing."""
    metric = FactRecallMetric()
    body = state.get("body", "")
    result = metric.evaluate(state["key_facts"], body)

    if result.score >= 0.5:
        return {"fact_score": result.score, "fact_feedback": ""}

    # Find which facts are missing
    missing = []
    for line in result.details.split("\n"):
        if "MISSING" in line:
            missing.append(line.strip())

    feedback = f"Missing key facts: {'; '.join(missing)}. "
    feedback += "Make sure ALL key facts are included in the email body."
    return {"fact_score": result.score, "fact_feedback": feedback}


def finalize(state: EmailState) -> dict:
    """Compute clarity score, assemble warnings, determine pass/fail."""
    subject = state.get("subject", "")
    body = state.get("body", "")
    clarity = ClarityConcisenessMetric().evaluate(subject, body)

    warnings: list[str] = []
    tone_score = state.get("tone_score", 1.0)
    fact_score = state.get("fact_score", 1.0)
    if tone_score < 0.5:
        warnings.append(f"Tone alignment low ({tone_score:.2f})")
    if fact_score < 0.5:
        warnings.append(f"Fact recall low ({fact_score:.2f})")
    if clarity.score < 0.5:
        warnings.append(f"Clarity low ({clarity.score:.2f})")

    retries = state.get("retry_count", 0)
    if retries >= MAX_RETRIES and warnings:
        warnings.append(f"Max retries ({MAX_RETRIES}) reached — review manually")

    passed = len(warnings) == 0

    return {
        "clarity_score": clarity.score,
        "warnings": warnings,
        "passed": passed,
    }


# ── Routing ──────────────────────────────────────────────────────────────────

def should_retry_tone(state: EmailState) -> str:
    """Retry if tone fails and we haven't exceeded max retries."""
    if state.get("tone_score", 1.0) >= 0.5:
        return "validate_facts"
    if state.get("retry_count", 0) >= MAX_RETRIES:
        return "finalize"
    return "generate_email"


def should_retry_facts(state: EmailState) -> str:
    """Retry if facts fail and we haven't exceeded max retries."""
    if state.get("fact_score", 1.0) >= 0.5:
        return "finalize"
    if state.get("retry_count", 0) >= MAX_RETRIES:
        return "finalize"
    return "generate_email"


# ── Graph ────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    builder = StateGraph(EmailState)

    builder.add_node("generate_email", generate_email)
    builder.add_node("validate_tone", validate_tone)
    builder.add_node("validate_facts", validate_facts)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "generate_email")
    builder.add_edge("generate_email", "validate_tone")
    builder.add_conditional_edges("validate_tone", should_retry_tone, {
        "generate_email": "generate_email",
        "validate_facts": "validate_facts",
        "finalize": "finalize",
    })
    builder.add_conditional_edges("validate_facts", should_retry_facts, {
        "generate_email": "generate_email",
        "finalize": "finalize",
    })
    builder.add_edge("finalize", END)

    return builder


# ── Public API ───────────────────────────────────────────────────────────────

def generate_with_guardrails(
    *,
    intent: str,
    key_facts: list[str],
    tone: str,
    model: str,
    strategy: str = "advanced",
) -> dict:
    """Run the full LangGraph pipeline. Returns dict with subject, body, scores, warnings."""
    graph = build_graph().compile()

    initial: EmailState = {
        "intent": intent,
        "key_facts": key_facts,
        "tone": tone,
        "model": model,
        "strategy": strategy,
        "retry_count": 0,
        "warnings": [],
        "passed": False,
    }

    state = graph.invoke(initial)

    # Reconstruct the prompt for output
    if strategy == "naive":
        prompt_template = build_naive_prompt(intent=intent, key_facts=key_facts, tone=tone)
    else:
        prompt_template = build_advanced_prompt(intent=intent, key_facts=key_facts, tone=tone)

    return {
        "subject": state.get("subject", ""),
        "body": state.get("body", ""),
        "tone_score": state.get("tone_score", 0.0),
        "fact_score": state.get("fact_score", 0.0),
        "clarity_score": state.get("clarity_score", 0.0),
        "warnings": state.get("warnings", []),
        "passed": state.get("passed", False),
        "retries": state.get("retry_count", 0),
        "prompt_template": prompt_template,
    }
