"""A/B evaluation runner — compares two models/strategies side-by-side.

Default: Model A (deepseek-v4-flash, advanced prompt) vs Model B (minimax-m3, naive prompt).
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path

from email_assistant.agents.pipeline import generate_with_guardrails
from email_assistant.config import Settings, get_settings
from email_assistant.evaluation.metrics import (
    ClarityConcisenessMetric,
    FactRecallMetric,
    ToneAlignmentMetric,
)
from email_assistant.evaluation.scenarios import TEST_SCENARIOS, TestScenario

RATE_LIMIT_DELAY = 20  # seconds between API calls to avoid 429

OUTPUT_DIR = Path("results")


@dataclass
class ModelConfig:
    name: str
    model: str
    strategy: str  # "advanced" or "naive"


DEFAULT_A = ModelConfig(
    name="OpenAI gpt-oss 120b + Advanced",
    model="openai/gpt-oss-120b",
    strategy="advanced",
)
DEFAULT_B = ModelConfig(
    name="MiniMax M3 + Naive",
    model="minimaxai/minimax-m3",
    strategy="naive",
)


def _eval(
    scenario: TestScenario,
    subject: str,
    body: str,
    prompt_template: str = "",
) -> dict:
    fact = FactRecallMetric().evaluate(scenario.key_facts, body)
    tone = ToneAlignmentMetric().evaluate(scenario.tone, body)
    clarity = ClarityConcisenessMetric().evaluate(subject, body)
    return {
        "scenario_id": scenario.id,
        "intent": scenario.intent,
        "tone": scenario.tone,
        "key_facts": scenario.key_facts,
        "generated_subject": subject,
        "generated_body": body,
        "reference_subject": scenario.reference_subject,
        "reference_body": scenario.reference_body,
        "prompt_template": prompt_template,
        "metrics": {
            "fact_recall": {"score": fact.score, "details": fact.details},
            "tone_alignment": {"score": tone.score, "details": tone.details},
            "clarity_conciseness": {
                "score": clarity.score,
                "details": clarity.details,
            },
        },
    }


def _averages(results: list[dict]) -> dict:
    if not results:
        return {
            "fact_recall": 0.0,
            "tone_alignment": 0.0,
            "clarity_conciseness": 0.0,
            "overall": 0.0,
        }
    fr = sum(r["metrics"]["fact_recall"]["score"] for r in results) / len(results)
    ta = sum(r["metrics"]["tone_alignment"]["score"] for r in results) / len(results)
    cc = (
        sum(r["metrics"]["clarity_conciseness"]["score"] for r in results)
        / len(results)
    )
    return {
        "fact_recall": round(fr, 4),
        "tone_alignment": round(ta, 4),
        "clarity_conciseness": round(cc, 4),
        "overall": round((fr + ta + cc) / 3, 4),
    }


def _run_model(
    cfg: ModelConfig,
    scenarios: list[TestScenario],
    settings: Settings,
) -> tuple[list[dict], dict]:
    results: list[dict] = []
    print(f"\n  [{cfg.name}] Running {len(scenarios)} scenarios...")

    for i, s in enumerate(scenarios, 1):
        print(f"    [{i}/{len(scenarios)}] {s.id}: {s.intent[:50]}...")
        try:
            out = generate_with_guardrails(
                intent=s.intent,
                key_facts=s.key_facts,
                tone=s.tone,
                model=cfg.model,
                strategy=cfg.strategy,
            )
            subject, body = out["subject"], out["body"]
            prompt = out["prompt_template"]
            print(
                f"      retries={out['retries']} passed={out['passed']}"
                f" — Subject: {subject}"
            )
            r = _eval(s, subject, body, prompt)
            r["generation_time_seconds"] = 0.0
            r["guardrail_warnings"] = out["warnings"]
            results.append(r)
        except Exception as exc:
            print(f"      ERROR: {exc}")
            results.append({
                "scenario_id": s.id,
                "intent": s.intent,
                "tone": s.tone,
                "key_facts": s.key_facts,
                "generated_subject": "ERROR",
                "generated_body": f"Failed: {exc}",
                "reference_subject": s.reference_subject,
                "reference_body": s.reference_body,
                "metrics": {
                    "fact_recall": {"score": 0.0, "details": str(exc)},
                    "tone_alignment": {"score": 0.0, "details": str(exc)},
                    "clarity_conciseness": {"score": 0.0, "details": str(exc)},
                },
                "generation_time_seconds": 0.0,
                "guardrail_warnings": [str(exc)],
            })
        time.sleep(RATE_LIMIT_DELAY)

    avgs = _averages(results)
    print(f"  [{cfg.name}] Overall: {avgs['overall']:.2%}")
    return results, avgs


def _write_analysis(
    a: ModelConfig,
    b: ModelConfig,
    ra: list[dict],
    rb: list[dict],
    aa: dict,
    ab: dict,
) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)

    winner_name = a.name if aa["overall"] >= ab["overall"] else b.name
    loser_name = b.name if winner_name == a.name else a.name
    aw = aa if winner_name == a.name else ab
    al = ab if winner_name == a.name else aa

    gaps = {
        k: aw[k] - al[k]
        for k in ["fact_recall", "tone_alignment", "clarity_conciseness"]
    }
    biggest_gap = max(gaps, key=gaps.get)  # type: ignore

    loser_r = rb if loser_name == b.name else ra
    worst = sorted(
        [
            (
                r["scenario_id"],
                r["metrics"]["fact_recall"]["score"]
                + r["metrics"]["tone_alignment"]["score"]
                + r["metrics"]["clarity_conciseness"]["score"],
            )
            for r in loser_r
            if r["generated_subject"] != "ERROR"
        ],
        key=lambda x: x[1],
    )[:3]

    fr_a, fr_b = aa["fact_recall"], ab["fact_recall"]
    ta_a, ta_b = aa["tone_alignment"], ab["tone_alignment"]
    cc_a, cc_b = aa["clarity_conciseness"], ab["clarity_conciseness"]
    ov_a, ov_b = aa["overall"], ab["overall"]

    md = f"""# Evaluation Summary

| Metric | {a.name} | {b.name} | Delta |
|---|---|---|---|
| Fact Recall | {fr_a:.2%} | {fr_b:.2%} | {fr_a - fr_b:+.2%} |
| Tone Alignment | {ta_a:.2%} | {ta_b:.2%} | {ta_a - ta_b:+.2%} |
| Clarity/Conciseness | {cc_a:.2%} | {cc_b:.2%} | {cc_a - cc_b:+.2%} |
| **Overall** | **{ov_a:.2%}** | **{ov_b:.2%}** | **{ov_a - ov_b:+.2%}** |

**Best performer:** {winner_name}

**Biggest failure mode of {loser_name}:**
{biggest_gap.replace("_", " ").title()} — {gaps[biggest_gap]:+.2%} difference.

**Worst scenarios for {loser_name}:**
{chr(10).join(f"- {sid}: {score:.2f}" for sid, score in worst)}

**Production recommendation:** {winner_name}. Scores +{(aw['overall'] - al['overall']):.2%} overall.
"""
    (OUTPUT_DIR / "analysis.md").write_text(md)

    with open(
        OUTPUT_DIR / "report.csv", "w", newline="", encoding="utf-8"
    ) as f:
        w = csv.writer(f)
        w.writerow([
            "model", "scenario", "intent", "tone",
            "fact_recall", "tone_alignment",
            "clarity_conciseness", "overall",
        ])
        for r in ra:
            fr_s = r["metrics"]["fact_recall"]["score"]
            ta_s = r["metrics"]["tone_alignment"]["score"]
            cc_s = r["metrics"]["clarity_conciseness"]["score"]
            avg = (fr_s + ta_s + cc_s) / 3
            w.writerow([
                a.name, r["scenario_id"], r["intent"], r["tone"],
                fr_s, ta_s, cc_s, round(avg, 4),
            ])
        for r in rb:
            fr_s = r["metrics"]["fact_recall"]["score"]
            ta_s = r["metrics"]["tone_alignment"]["score"]
            cc_s = r["metrics"]["clarity_conciseness"]["score"]
            avg = (fr_s + ta_s + cc_s) / 3
            w.writerow([
                b.name, r["scenario_id"], r["intent"], r["tone"],
                fr_s, ta_s, cc_s, round(avg, 4),
            ])
        w.writerow([])
        w.writerow([
            a.name, "", "", "AVG",
            aa["fact_recall"], aa["tone_alignment"],
            aa["clarity_conciseness"], aa["overall"],
        ])
        w.writerow([
            b.name, "", "", "AVG",
            ab["fact_recall"], ab["tone_alignment"],
            ab["clarity_conciseness"], ab["overall"],
        ])

    return OUTPUT_DIR / "analysis.md"


def run_evaluation(
    config_a: ModelConfig | None = None,
    config_b: ModelConfig | None = None,
) -> dict:
    a = config_a or DEFAULT_A
    b = config_b or DEFAULT_B
    settings = get_settings()

    print(f"\n{'='*70}")
    print("EMAIL GENERATION ASSISTANT — A/B EVALUATION")
    print(f"{'='*70}")
    print(f"Model A: {a.name} ({a.model}, {a.strategy} prompt)")
    print(f"Model B: {b.name} ({b.model}, {b.strategy} prompt)")
    print(f"Scenarios: {len(TEST_SCENARIOS)}")

    ra, aa = _run_model(a, TEST_SCENARIOS, settings)
    print(f"\n  Pausing {RATE_LIMIT_DELAY}s before switching models...")
    time.sleep(RATE_LIMIT_DELAY)
    rb, ab = _run_model(b, TEST_SCENARIOS, settings)

    report = {
        "metric_definitions": {
            "fact_recall": {
                "name": "Fact Recall Score",
                "description": "Whether all input facts appear in the output.",
                "scoring": "0.0-1.0",
            },
            "tone_alignment": {
                "name": "Tone Alignment Score",
                "description": "Whether the email matches the requested tone.",
                "scoring": "0.0-1.0",
            },
            "clarity_conciseness": {
                "name": "Clarity & Conciseness Score",
                "description": "Readability, appropriate length, no redundancy.",
                "scoring": "0.0-1.0",
            },
        },
        "model_a": {
            "name": a.name,
            "model": a.model,
            "strategy": a.strategy,
        },
        "model_b": {
            "name": b.name,
            "model": b.model,
            "strategy": b.strategy,
        },
        "model_a_results": ra,
        "model_b_results": rb,
        "model_a_averages": aa,
        "model_b_averages": ab,
        "summary": {
            "total_scenarios": len(TEST_SCENARIOS),
            "winner": a.name if aa["overall"] >= ab["overall"] else b.name,
            "overall_delta": round(abs(aa["overall"] - ab["overall"]), 4),
        },
    }

    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_analysis(a, b, ra, rb, aa, ab)

    print(f"\n{'='*70}")
    print("COMPLETE")
    print(f"{'='*70}")
    print(f"{'Metric':<25} {a.name:>35} {b.name:>35}")
    print("-" * 97)
    print(f"{'Fact Recall':<25} {aa['fact_recall']:>34.2%} {ab['fact_recall']:>34.2%}")
    print(
        f"{'Tone Alignment':<25} {aa['tone_alignment']:>34.2%}"
        f" {ab['tone_alignment']:>34.2%}"
    )
    print(
        f"{'Clarity/Conciseness':<25} {aa['clarity_conciseness']:>34.2%}"
        f" {ab['clarity_conciseness']:>34.2%}"
    )
    print(f"{'OVERALL':<25} {aa['overall']:>34.2%} {ab['overall']:>34.2%}")
    print(f"\nWinner: {report['summary']['winner']}")
    print("Outputs: results/report.json, results/report.csv, results/analysis.md\n")

    return report


def main() -> None:
    run_evaluation()


if __name__ == "__main__":
    main()
