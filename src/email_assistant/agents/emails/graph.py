"""LangGraph agent for email generation."""

from __future__ import annotations

import asyncio
from typing import cast

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from email_assistant.agents.emails.prompts import build_email_generation_prompt
from email_assistant.agents.emails.schema import EmailDraft
from email_assistant.agents.llm import get_llm
from email_assistant.config import Settings, get_settings

logger = structlog.get_logger()


class EmailGenerationAgent:
    """Agent that generates professional emails using advanced prompt engineering.

    Uses a combination of Role-Playing, Chain-of-Thought, and Few-Shot prompting
    techniques to maximize output quality and reliability.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        llm: object | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._llm = llm or get_llm(self._settings)

    async def generate(
        self,
        *,
        intent: str,
        key_facts: list[str],
        tone: str,
    ) -> EmailDraft:
        """Generate a professional email from intent, key facts, and tone."""
        prompt_text = build_email_generation_prompt(
            intent=intent,
            key_facts=key_facts,
            tone=tone,
        )
        logger.info(
            "email_generation_calling_llm",
            intent=intent,
            tone=tone,
            facts_count=len(key_facts),
            prompt_length=len(prompt_text),
        )

        timeout_seconds = self._settings.email_llm_timeout_seconds
        llm = cast("BaseChatModel", self._llm)
        structured_llm = llm.with_structured_output(EmailDraft)

        try:
            invocation = structured_llm.ainvoke([HumanMessage(content=prompt_text)])
            result = cast(
                "EmailDraft",
                await asyncio.wait_for(invocation, timeout=timeout_seconds)
                if timeout_seconds > 0
                else await invocation,
            )
        except TimeoutError as exc:
            logger.warning(
                "email_generation_llm_timeout",
                timeout_seconds=timeout_seconds,
            )
            raise RuntimeError("LLM response timed out before producing an email draft.") from exc

        logger.info(
            "email_generation_complete",
            subject=result.subject,
            body_length=len(result.body),
        )
        return result
