"""Evaluation components for the email generation assistant."""

from __future__ import annotations

from email_assistant.evaluation.metrics import (
    ClarityConcisenessMetric,
    FactRecallMetric,
    ToneAlignmentMetric,
)
from email_assistant.evaluation.scenarios import TEST_SCENARIOS, TestScenario

__all__ = [
    "ClarityConcisenessMetric",
    "FactRecallMetric",
    "TEST_SCENARIOS",
    "TestScenario",
    "ToneAlignmentMetric",
]
