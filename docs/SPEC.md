# Email Generation Assistant — Project Specification

## Overview

An AI-powered email generation system that produces professional emails from structured inputs using NVIDIA LLMs. Accepts three inputs — **intent**, **key facts**, and **tone** — and returns a complete email (subject + body). Includes an A/B evaluation framework comparing two models/strategies with 3 custom metrics across 10 test scenarios.

**Stack:** Python 3.13+, FastAPI, LangChain + ChatNVIDIA, Pydantic v2.

---

## Requirements

### Functional

| ID | Requirement |
|---|---|
| FR-1 | Accept intent (string), key_facts (list), tone (string) |
| FR-2 | Generate email with subject line and body |
| FR-3 | Incorporate all key facts naturally |
| FR-4 | Match requested tone |
| FR-5 | Run 10 evaluation scenarios and produce JSON/CSV/markdown report |
| FR-6 | Compare two models/strategies using same metrics |

### Prompt Engineering

**Strategy A — Advanced (Role-Playing + Chain-of-Thought + Few-Shot):**

```
Role: "world-class email writer with 15 years experience" →
CoT: UNDERSTAND → ORGANIZE → MATCH → CRAFT → WRITE →
Few-Shot: 4 reference emails (formal, casual, urgent, empathetic) →
User request
```

**Strategy B — Naive (baseline):**

```
"Write an email. Intent: X. Facts: Y. Tone: Z"
```

### Evaluation

**3 Custom Metrics:**

| Metric | Technique | Range |
|---|---|---|
| **Fact Recall** | Keyword extraction + coverage per fact (40% threshold) | 0.0–1.0 |
| **Tone Alignment** | Lexical analysis of tone indicators + contradiction penalty | 0.0–1.0 |
| **Clarity & Conciseness** | Sentence length + word count bounds + redundancy + subject quality | 0.0–1.0 |

**Output:** `results/report.json` (full data), `results/report.csv` (side-by-side), `results/analysis.md` (one-page summary with recommendation).

---

## Architecture

```
┌──────────────────────────────────────────────┐
│  FastAPI (/generate, /health)                │
└──────────────┬───────────────────────────────┘
               │
┌──────────────▼───────────────────────────────┐
│  LangGraph Pipeline (pipeline.py)            │
│                                              │
│  ┌────────────┐    ┌──────────────────┐      │
│  │ generate_  │───▶│ validate_tone    │      │
│  │ email      │    │ (tone guardrail) │      │
│  └────────────┘    └────────┬─────────┘      │
│       ▲              pass/  │ fail            │
│       │              ┌─────┘                 │
│       └──────────────┘ (retry ≤2)            │
│                          │ pass              │
│               ┌──────────▼──────────┐        │
│               │ validate_facts      │        │
│               │ (fact guardrail)    │        │
│               └──────────┬──────────┘        │
│                    pass/ │ fail              │
│                    ┌─────┘                   │
│                    └──────────────────┐      │
│                          │ pass       │      │
│               ┌──────────▼──────────┐ │      │
│               │ finalize            │◀┘      │
│               │ (clarity + warnings)│        │
│               └─────────────────────┘        │
└──────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────┐
│  ChatNVIDIA (langchain-nvidia-ai-endpoints)  │
│  Model A: deepseek-v4-flash (advanced prompt)│
│  Model B: minimax-m3 (naive prompt)          │
└──────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────┐
│  Evaluation (evaluation/)                    │
│  scenarios.py — 10 test scenarios            │
│  metrics.py — 3 custom metrics               │
│  run_evaluation.py — A/B comparison          │
│  → results/{report.json, report.csv,         │
│             analysis.md}                     │
└──────────────────────────────────────────────┘
```

### LangGraph Pipeline

The pipeline uses `StateGraph` with conditional retry edges:

1. **generate_email** — calls ChatNVIDIA with structured output
2. **validate_tone** — `ToneAlignmentMetric` check; if < 0.5, provides feedback and triggers retry
3. **validate_facts** — `FactRecallMetric` check; if < 0.5, finds missing facts and triggers retry
4. **finalize** — `ClarityConcisenessMetric` check, assembles warnings, determines pass/fail

Max 2 retries. If still failing after retries, warnings are emitted but generation completes.

### LLM Provider

All calls go through `ChatNVIDIA` (`langchain-nvidia-ai-endpoints`):

| Config | Model | Use |
|---|---|---|
| Model A | `deepseek-ai/deepseek-v4-flash` | Default / advanced prompt |
| Model B | `minimaxai/minimax-m3` | Comparison / naive prompt |

Configured via `.env` — no code changes to switch models.

### Project Structure

```
src/email_assistant/
├── agents/
│   ├── emails.py       # Prompt templates + generation functions
│   ├── llm.py          # ChatNVIDIA factory
│   ├── pipeline.py     # LangGraph pipeline with guardrails
│   └── schema.py       # EmailDraft Pydantic model
├── config.py           # Settings (env vars)
├── evaluation/
│   ├── metrics.py      # FactRecall, ToneAlignment, ClarityConciseness
│   ├── scenarios.py    # 10 test scenarios + human references
│   └── run_evaluation.py  # A/B comparison runner
└── main.py             # FastAPI app
```
