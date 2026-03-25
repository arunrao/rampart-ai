"""Security behavior of HTTP middleware (auth gate, size limits, headers)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.security
def test_missing_authorization_returns_401(client: TestClient):
    r = client.get("/api/v1/policies")
    assert r.status_code == 401
    body = r.json()
    assert body.get("error") == "Authentication required"
    assert "Missing Authorization header" in body.get("detail", "")


@pytest.mark.security
def test_malformed_bearer_returns_401(client: TestClient):
    r = client.get(
        "/api/v1/policies",
        headers={"Authorization": "NotBearer x.y.z"},
    )
    assert r.status_code == 401


@pytest.mark.security
def test_bearer_token_without_jwt_shape_returns_401(client: TestClient):
    r = client.get(
        "/api/v1/policies",
        headers={"Authorization": "Bearer notvalidtoken"},
    )
    assert r.status_code == 401


@pytest.mark.security
def test_public_health_unauthenticated(client: TestClient):
    assert client.get("/api/v1/health").status_code == 200


@pytest.mark.security
def test_public_providers_supported_unauthenticated(client: TestClient):
    r = client.get("/api/v1/providers/supported")
    assert r.status_code == 200


@pytest.mark.security
def test_oauth_login_path_unauthenticated(client: TestClient):
    # Do not follow redirect to accounts.google.com (would hit API middleware on test client).
    r = client.get("/api/v1/auth/google/login", follow_redirects=False)
    assert r.status_code in (302, 307, 400, 500)


@pytest.mark.security
def test_security_headers_present(client: TestClient):
    r = client.get("/api/v1/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in r.headers


@pytest.mark.security
@pytest.mark.slow
def test_content_length_over_limit_returns_413(client: TestClient, auth_headers: dict):
    body = b"x" * (11_000_000)
    r = client.post(
        "/api/v1/filter",
        headers={**auth_headers, "Content-Length": str(len(body))},
        content=body,
    )
    assert r.status_code == 413
