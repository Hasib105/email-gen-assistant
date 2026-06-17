FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/api/src apps/api/src

RUN uv sync --no-dev --package case-assistant-api

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "case_assistant_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
