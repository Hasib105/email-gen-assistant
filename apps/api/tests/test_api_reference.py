from __future__ import annotations

from typing import cast

from case_assistant_api.main import create_app
from fastapi.testclient import TestClient
from httpx import Response


def test_scalar_api_reference_returns_html() -> None:
    client = TestClient(create_app())

    response = cast("Response", client.get("/scalar"))

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Case Assistant API Reference" in response.text
