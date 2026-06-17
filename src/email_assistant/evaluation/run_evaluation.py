"""Evaluation runner for the email generation assistant.

Runs 10 test scenarios through the email generation agent, evaluates each
using 3 custom metrics, and outputs a structured evaluation report.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import structlog

from email_assistant.agents.emails.graph import EmailGenerationAgent
from email_assistant.evaluation.metrics import (
    ClarityConcisenessMetric,
    FactRecallMetric,
    MetricResult,
    ToneAlignmentMetric,
)
from email_assistant.evaluation.scenarios import TEST_SCENARIOS, TestScenario

logger = structlog.get_logger()

OUTPUT_FILE = "evaluation_report.json"


def evaluate_scenario(
    scenario: TestScenario,
    generated_subject: str,
    generated_body: str,
) -> dict:
    """Evaluate a single scenario against all 3 custom metrics."""
    fact_metric = FactRecallMetric()
    tone_metric = ToneAlignmentMetric()
    clarity_metric = ClarityConcisenessMetric()

    fact_result = fact_metric.evaluate(scenario.key_facts, generated_body)
    tone_result = tone_metric.evaluate(scenario.tone, generated_body)
    clarity_result = clarity_metric.evaluate(generated_subject, generated_body)

    return {
        "scenario_id": scenario.id,
        "intent": scenario.intent,
        "tone": scenario.tone,
        "key_facts": scenario.key_facts,
        "generated_subject": generated_subject,
        "generated_body": generated_body,
        "reference_subject": scenario.reference_subject,
        "reference_body": scenario.reference_body,
        "metrics": {
            "fact_recall": {
                "score": fact_result.score,
                "details": fact_result.details,
            },
            "tone_alignment": {
                "score": tone_result.score,
                "details": tone_result.details,
            },
            "clarity_conciseness": {
                "score": clarity_result.score,
                "details": clarity_result.details,
            },
        },
    }


def calculate_averages(results: list[dict]) -> dict:
    """Calculate overall average scores across all scenarios."""
    if not results:
        return {"fact_recall": 0.0, "tone_alignment": 0.0, "clarity_conciseness": 0.0, "overall": 0.0}

    fact_scores = [r["metrics"]["fact_recall"]["score"] for r in results]
    tone_scores = [r["metrics"]["tone_alignment"]["score"] for r in results]
    clarity_scores = [r["metrics"]["clarity_conciseness"]["score"] for r in results]

    avg_fact = sum(fact_scores) / len(fact_scores)
    avg_tone = sum(tone_scores) / len(tone_scores)
    avg_clarity = sum(clarity_scores) / len(clarity_scores)
    overall = (avg_fact + avg_tone + avg_clarity) / 3

    return {
        "fact_recall": round(avg_fact, 4),
        "tone_alignment": round(avg_tone, 4),
        "clarity_conciseness": round(avg_clarity, 4),
        "overall": round(overall, 4),
    }


async def run_evaluation() -> dict:
    """Run all test scenarios and generate the evaluation report."""
    agent = EmailGenerationAgent()
    results: list[dict] = []

    print(f"\n{'='*70}")
    print("EMAIL GENERATION ASSISTANT — EVALUATION RUN")
    print(f"{'='*70}")
    print(f"Running {len(TEST_SCENARIOS)} test scenarios...\n")

    for i, scenario in enumerate(TEST_SCENARIOS, 1):
        print(f"[{i}/{len(TEST_SCENARIOS)}] Scenario: {scenario.id}")
        print(f"  Intent: {scenario.intent}")
        print(f"  Tone: {scenario.tone}")

        start_time = time.time()
        try:
            email_draft = await agent.generate(
                intent=scenario.intent,
                key_facts=scenario.key_facts,
                tone=scenario.tone,
            )
            elapsed = time.time() - start_time
            print(f"  Generated in {elapsed:.2f}s")
            print(f"  Subject: {email_draft.subject}")

            result = evaluate_scenario(scenario, email_draft.subject, email_draft.body)
            result["generation_time_seconds"] = round(elapsed, 3)
            results.append(result)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            logger.error("evaluation_scenario_failed", scenario_id=scenario.id, error=str(exc))
            results.append({
                "scenario_id": scenario.id,
                "intent": scenario.intent,
                "tone": scenario.tone,
                "key_facts": scenario.key_facts,
                "generated_subject": "ERROR",
                "generated_body": f"Generation failed: {exc}",
                "reference_subject": scenario.reference_subject,
                "reference_body": scenario.reference_body,
                "metrics": {
                    "fact_recall": {"score": 0.0, "details": f"Error: {exc}"},
                    "tone_alignment": {"score": 0.0, "details": f"Error: {exc}"},
                    "clarity_conciseness": {"score": 0.0, "details": f"Error: {exc}"},
                },
                "generation_time_seconds": round(time.time() - start_time, 3),
            })

    averages = calculate_averages(results)

    report = {
        "metric_definitions": {
            "fact_recall": {
                "name": "Fact Recall Score",
                "description": (
                    "Measures whether all key facts from the input are included in the "
                    "generated email. Uses keyword extraction and coverage analysis to "
                    "check if core concepts from each fact appear in the email body."
                ),
                "scoring": "0.0 (no facts recalled) to 1.0 (all facts perfectly included)",
            },
            "tone_alignment": {
                "name": "Tone Alignment Score",
                "description": (
                    "Evaluates how well the generated email matches the requested tone. "
                    "Uses lexical analysis of tone-indicative words and checks for "
                    "contradicting language patterns."
                ),
                "scoring": "0.0 (completely wrong tone) to 1.0 (perfect tone match)",
            },
            "clarity_conciseness": {
                "name": "Clarity & Conciseness Score",
                "description": (
                    "Assesses readability, appropriate length, redundancy, and subject "
                    "line quality. Combines sentence length analysis, word count bounds, "
                    "phrase repetition detection, and subject word count."
                ),
                "scoring": "0.0 (unclear/verbose) to 1.0 (crystal clear and concise)",
            },
        },
        "scenarios_results": results,
        "overall_averages": averages,
        "summary": {
            "total_scenarios": len(results),
            "scenarios_with_errors": sum(1 for r in results if r["generated_subject"] == "ERROR"),
            "best_performing_scenario": max(
                (r["scenario_id"] for r in results),
                key=lambda sid: next(
                    r["metrics"]["fact_recall"]["score"]
                    + r["metrics"]["tone_alignment"]["score"]
                    + r["metrics"]["clarity_conciseness"]["score"]
                    for r in results
                    if r["scenario_id"] == sid
                ),
            ) if results else "N/A",
            "worst_performing_scenario": min(
                (r["scenario_id"] for r in results),
                key=lambda sid: next(
                    r["metrics"]["fact_recall"]["score"]
                    + r["metrics"]["tone_alignment"]["score"]
                    + r["metrics"]["clarity_conciseness"]["score"]
                    for r in results
                    if r["scenario_id"] == sid
                ),
            ) if results else "N/A",
        },
    }

    output_path = Path(OUTPUT_FILE)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n{'='*70}")
    print("EVALUATION COMPLETE")
    print(f"{'='*70}")
    print(f"Results saved to: {OUTPUT_FILE}")
    print(f"\nOverall Averages:")
    print(f"  Fact Recall:        {averages['fact_recall']:.2%}")
    print(f"  Tone Alignment:     {averages['tone_alignment']:.2%}")
    print(f"  Clarity/Conciseness:{averages['clarity_conciseness']:.2%}")
    print(f"  OVERALL:            {averages['overall']:.2%}")
    print(f"{'='*70}\n")

    return report


def main() -> None:
    """Entry point for running the evaluation."""
    asyncio.run(run_evaluation())


if __name__ == "__main__":
    main()
