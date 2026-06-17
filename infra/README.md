# Infrastructure

Local infrastructure mirrors the planned production dependencies without requiring production credentials.

```bash
docker compose -f infra/compose/docker-compose.yml up postgres redis opensearch qdrant -d
```

Services:

- Postgres for local structured case data.
- Redis for background draft jobs.
- OpenSearch for SOP/history retrieval.
- Qdrant for vector evidence retrieval.
- API container profile for full-container smoke tests.

Seed local data after starting Docker (empty databases before the first run are normal):

```bash
docker compose -f infra/compose/docker-compose.yml up postgres redis opensearch -d
uv run python scripts/seed.py
```
