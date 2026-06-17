# Email Generation Assistant

AI-powered email generation using NVIDIA LLMs with A/B evaluation framework.

## What it does

Takes three inputs — **intent**, **key facts**, and **tone** — and generates a professional email. Compares two models/strategies side-by-side using 3 custom evaluation metrics across 10 test scenarios.

## Quick start

```bash
# Install
uv sync

# Set API key
cp .env.example .env
# Edit .env → add your NVIDIA_API_KEY

# Run API
uv run uvicorn email_assistant.main:app --reload

# Run A/B evaluation
uv run python -m email_assistant.evaluation
```

## Models (NVIDIA API)

| Config | Model | Prompt Strategy |
|---|---|---|
| Model A | `deepseek-ai/deepseek-v4-flash` | Advanced (Role + CoT + Few-Shot) |
| Model B | `minimaxai/minimax-m3` | Naive (baseline) |

Uses `langchain-nvidia-ai-endpoints` ChatNVIDIA with structured output.

## Evaluation

- **10 test scenarios** covering 6 tones (professional, formal, casual, urgent, empathetic, enthusiastic)
- **3 custom metrics**: Fact Recall, Tone Alignment, Clarity & Conciseness
- **Output**: `results/report.json`, `results/report.csv`, `results/analysis.md`

## Project structure

```
src/email_assistant/
├── agents/
│   ├── emails.py       # Prompt templates + generation via ChatNVIDIA
│   ├── llm.py          # ChatNVIDIA factory
│   └── schema.py       # EmailDraft Pydantic model
├── config.py           # Settings (NVIDIA API config)
├── evaluation/
│   ├── metrics.py      # 3 custom metrics
│   ├── scenarios.py    # 10 test scenarios + references
│   └── run_evaluation.py  # A/B comparison runner
└── main.py             # FastAPI app
```
