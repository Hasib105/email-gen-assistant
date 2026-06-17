"""Prompt templates for the case draft graph."""

from __future__ import annotations

from case_assistant_api.domains.rag.retriever import Evidence


def build_customer_reply_prompt(
    *,
    masked_context: str,
    evidence: list[Evidence],
    user_question: str = "",
    response_language: str = "English",
) -> str:
    """Build the full prompt sent to the LLM.

    If the agent supplied a question, the LLM is asked to answer it directly.
    Otherwise it is asked to summarise the case and recommend next actions.
    """
    evidence_block = (
        "\n".join(f"- {item.title}: {item.excerpt}" for item in evidence)
        or "- No policy evidence was retrieved."
    )

    if user_question.strip():
        task_instruction = (
            f"Answer the following agent question concisely and accurately:\n{user_question}"
        )
    else:
        task_instruction = (
            "Provide a concise case summary and recommend the best next actions "
            "for the support agent to take on behalf of the customer."
        )

    return (
        "You are a helpful travel support AI assistant. "
        "Draft a professional, accurate response for human agent review.\n"
        "Base your response strictly on the case context and policy evidence provided.\n"
        "Never reveal raw personal data. Use masked placeholders only "
        "(for example CUSTOMER_1, PHONE_1, BOOKING_REF_1 when needed).\n"
        "Keep the customer-facing reply short, specific, and non-repetitive. "
        "Prefer 2-4 concise paragraphs or bullets with clear next steps.\n\n"
        f"Write the customer-facing reply in {response_language}.\n\n"
        f"Case context:\n{masked_context}\n\n"
        f"Policy evidence:\n{evidence_block}\n\n"
        f"Task: {task_instruction}"
    )
