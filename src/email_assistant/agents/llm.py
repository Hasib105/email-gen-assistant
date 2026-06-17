"""LLM client — uses NVIDIA API via langchain-nvidia-ai-endpoints."""

from __future__ import annotations

from langchain_nvidia_ai_endpoints import ChatNVIDIA

from email_assistant.config import Settings, get_settings


def get_llm(model: str | None = None, settings: Settings | None = None) -> ChatNVIDIA:
    """Create a ChatNVIDIA instance for the given model."""
    cfg = settings or get_settings()
    return ChatNVIDIA(
        model=model or cfg.nvidia_model_a,
        api_key=cfg.nvidia_api_key,
        base_url=cfg.nvidia_base_url,
        temperature=cfg.nvidia_temperature,
        top_p=cfg.nvidia_top_p,
        max_tokens=cfg.nvidia_max_tokens,
    )
