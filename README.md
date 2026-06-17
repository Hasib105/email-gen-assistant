# Email Generation Assistant

AI-powered email generation assistant that creates professional emails based on user input using an LLM with advanced prompt engineering.

## Overview

The assistant takes three distinct inputs and produces a well-written, professional email:

1. **Intent**: The core purpose of the email (e.g., "Follow up after meeting", "Request for proposal details")
2. **Key Facts**: Bullet points of information to include in the email
3. **Tone**: The desired style (e.g., formal, casual, urgent, empathetic)

## Tech Stack

- Python 3.13+ with `uv`
- FastAPI + Uvicorn
- LangGraph for agent orchestration
- LangChain (Gemini / OpenAI) for LLM integration
- LangGraph Checkpoint (SQLite/Postgres) for state persistence
- OpenSearch / Qdrant for RAG retrieval
- Pydantic for data validation
- structlog for logging
- pytest + Ruff + Pyright for quality

## First-Time Setup

```bash
uv sync
cp .env.example .env
docker compose -f infra/compose/docker-compose.yml up postgres redis opensearch -d
```

## Daily Dev Loop

```bash
uv run uvicorn case_assistant_api.main:app --reload --host 0.0.0.0 --port 8000
```

Open:
- API health: http://localhost:8000/health
- OpenAPI: http://localhost:8000/openapi.json
- Swagger UI: http://localhost:8000/docs
- Scalar API Reference: http://localhost:8000/scalar

## Quality Gates

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

## API Usage

### Generate an Email

```bash
curl -X POST http://localhost:8000/emails/generate \
  -H "Content-Type: application/json" \
  -d '{
    "intent": "Follow up after networking event",
    "key_facts": ["Met at Tech Conference 2026", "Discussed potential collaboration on AI project", "Available for coffee chat next week"],
    "tone": "professional"
  }'
```

### Run Evaluation

```bash
uv run python -m case_assistant_api.evaluation.run_evaluation
```

## Project Structure

```text
apps/
  api/             FastAPI app, domain services, tests
docs/
  README.md        Quick index for project documentation
  AI_AGENT_GUIDELINES.md
                   Start-here guide for AI-assisted coding work
infra/
  compose/         Local Postgres, Redis, OpenSearch
  dockerfiles/     API container definition
scripts/           Dev helpers
evaluation/        Test scenarios, metrics, and evaluation runner
```

## Evaluation Metrics

The project implements 3 custom evaluation metrics:

1. **Fact Recall Score** - Measures whether all key facts from the input are included in the generated email
2. **Tone Alignment Score** - Evaluates how well the email matches the requested tone
3. **Clarity & Conciseness Score** - Assesses readability, grammar, and appropriate length

Run the full evaluation suite:

```bash
uv run python -m case_assistant_api.evaluation.run_evaluation
```

Output: `evaluation_report.json` with raw scores and averages.
