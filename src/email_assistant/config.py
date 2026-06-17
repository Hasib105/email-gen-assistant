"""Application settings — NVIDIA models only."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    nvidia_api_key: str = ""
    nvidia_model_a: str = "deepseek-ai/deepseek-v4-flash"
    nvidia_model_b: str = "minimaxai/minimax-m3"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_max_tokens: int = 16384
    nvidia_temperature: float = 1.0
    nvidia_top_p: float = 0.95
    email_llm_timeout_seconds: float = 60.0
    response_language: str = "English"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
