"""HTTP-level security checks across routers."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.security
def test_filter_requires_authentication(client: TestClient):
    r = client.post(
        "/api/v1/filter",
        json={"content": "hello", "filters": ["pii"]},
    )
    assert r.status_code == 401


@pytest.mark.security
def test_filter_accepts_valid_jwt(client: TestClient, auth_headers: dict):
    r = client.post(
        "/api/v1/filter",
        headers=auth_headers,
        json={"content": "Hello world", "filters": ["toxicity"], "redact": False},
    )
    assert r.status_code == 200
    data = r.json()
    assert "is_safe" in data


@pytest.mark.security
def test_sql_injection_payload_in_json_does_not_crash(client: TestClient, auth_headers: dict):
    payload = "'; DROP TABLE users; --"
    r = client.post(
        "/api/v1/filter",
        headers=auth_headers,
        json={"content": payload, "filters": ["pii"], "redact": False},
    )
    assert r.status_code == 200


@pytest.mark.security
def test_extremely_long_string_bounded_by_app(client: TestClient, auth_headers: dict):
    r = client.post(
        "/api/v1/filter",
        headers=auth_headers,
        json={"content": "x" * 50_000, "filters": ["toxicity"], "redact": False},
    )
    assert r.status_code in (200, 400, 413, 422)
