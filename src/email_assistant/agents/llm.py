"""LLM provider factory.

Returns a LangChain chat model based on ``Settings.llm_provider``.
Default provider is Google Gemini via ``langchain-google-genai``.
OpenAI is available as a fallback (requires the ``llm`` optional extra).
"""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import cast

from langchain_core.language_models import BaseChatModel

from case_assistant_api.config import Settings, get_settings


def get_llm(settings: Settings | None = None) -> BaseChatModel:
    """Instantiate and return a chat model for the configured provider."""
    cfg = settings or get_settings()

    if cfg.llm_provider.lower() in {"gemini", "google"}:
        from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: PLC0415

        return ChatGoogleGenerativeAI(  # type: ignore[return-value]
            model=cfg.llm_model,
            google_api_key=cfg.gemini_api_key or None,  # type: ignore[arg-type]
            temperature=0.3,
            max_output_tokens=cfg.email_llm_max_output_tokens,
        )

    try:
        openai_module = import_module("langchain_openai")
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install the `llm` optional extra to use OpenAI models.") from exc

    chat_openai = cast("Callable[..., BaseChatModel]", openai_module.__dict__["ChatOpenAI"])
    return chat_openai(
        model=cfg.llm_model,
        api_key=cfg.openai_api_key or None,
        temperature=0.3,
        max_tokens=cfg.email_llm_max_output_tokens,
    )
