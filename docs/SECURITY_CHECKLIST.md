# Security Checklist

Status legend:

- Done: implemented and covered by tests.
- Partial: implemented for demo or local paths, but not fully production hardened.
- Not implemented: required before production.

## Secrets

Status: Partial

- Secrets are loaded from environment variables.
- `.env` files are ignored by git.
- `.env.example` contains placeholders only.
- Production secret-manager integration is not implemented.

## PII Masking

Status: Done for demo, Partial for production

- Known customer name, email, phone values are masked.
- Generic emails and phone numbers are masked.
- Production-grade entity detection is not implemented.

## LLM Output Scan

Status: Done for demo, Partial for production

- Generated email content is scanned before output.
- Detected raw sensitive values are masked and a human-review warning is added.
- Full policy/factuality validation is not implemented.

## Logging Redaction

Status: Done for demo, Partial for production

- Structlog events pass through a central redaction processor.
- Common emails, phones, and API keys are redacted.
- Production observability still needs request IDs, metrics, tracing, and log retention policy.

## DB Access

Status: Partial

- Fixture data is separated from the PostgreSQL adapter.
- PostgreSQL access is parameterized for case ID lookup.
- Connection pooling, migrations, SSL configuration, and integration tests are not implemented.

## RAG Retrieval

Status: Partial

- Static, OpenSearch, and Qdrant retrieval seams exist.
- Static retrieval supports the demo.
- OpenSearch/Qdrant are not production hardened and need indexing, auth/TLS, ranking, and evaluation work.

## Production Blockers

Before production, complete at minimum:

- Durable queue and worker.
- Production database schema and migrations.
- Hardened OpenSearch/RAG pipeline.
- Secrets manager integration.
- Full deployment and incident runbooks.
