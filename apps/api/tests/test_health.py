from __future__ import annotations

from typing import cast

from case_assistant_api.main import create_app
from fastapi.testclient import TestClient
from httpx import Response


def test_health_returns_ok() -> None:
    client = TestClient(create_app())

    response = cast("Response", client.get("/health"))

    assert response.status_code == 200
    payload = cast("dict[str, object]", response.json())
    assert payload["status"] == "ok"
    assert payload["service"] == "case-assistant-api"
