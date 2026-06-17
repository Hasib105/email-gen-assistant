"""Minimal test suite for email generation assistant."""

from __future__ import annotations

import pytest
from email_assistant.agents.emails import build_advanced_prompt, build_naive_prompt
from email_assistant.config import Settings


def test_advanced_prompt_contains_all_parts():
    prompt = build_advanced_prompt(intent="Test", key_facts=["fact1", "fact2"], tone="formal")
    assert "world-class" in prompt
    assert "fact1" in prompt
    assert "fact2" in prompt
    assert "formal" in prompt.lower()


def test_naive_prompt_is_minimal():
    prompt = build_naive_prompt(intent="Test", key_facts=["fact1", "fact2"], tone="casual")
    assert "Write an email" in prompt
    assert "fact1" in prompt
    assert "fact2" in prompt


def test_settings_loads():
    s = Settings()
    assert s.nvidia_model_a == "deepseek-ai/deepseek-v4-flash"
    assert s.nvidia_model_b == "minimaxai/minimax-m3"
    assert s.nvidia_base_url == "https://integrate.api.nvidia.com/v1"
