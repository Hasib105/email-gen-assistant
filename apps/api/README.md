# Email Generation Assistant API

FastAPI application for AI-powered email generation.

## Run

```bash
uv run uvicorn case_assistant_api.main:app --reload --host 0.0.0.0 --port 8000
```

## Local Smoke

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/emails/generate \
  -H "Content-Type: application/json" \
  -d '{"intent": "Follow up", "key_facts": ["Met at conference"], "tone": "professional"}'
```

## API Reference

- OpenAPI JSON: http://localhost:8000/openapi.json
- Swagger UI: http://localhost:8000/docs
- Scalar API Reference: http://localhost:8000/scalar

## Package Layout

```text
case_assistant_api/
  api/          HTTP routers
  agents/       LLM agents (drafts, emails)
  domains/      testable product behavior
  evaluation/   custom metrics and test scenarios
  security/     output guardrails and authorization
  workers/      background job seam
```

Routers should remain thin. Domain services are the reusable contract for FastAPI handlers, workers, and LangGraph nodes.
