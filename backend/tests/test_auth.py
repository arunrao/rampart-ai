"""
Authentication helpers and JWT behavior (Google OAuth is primary; password routes removed).
"""
from __future__ import annotations

import uuid

import jwt
import pytest
from fastapi.testclient import TestClient

from api.config import get_settings
from api.routes.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


@pytest.mark.unit
def test_hash_and_verify_password_roundtrip():
    h = hash_password("correct horse battery")
    assert verify_password("correct horse battery", h)
    assert not verify_password("wrong", h)


@pytest.mark.unit
def test_create_and_decode_access_token():
    from tests.helpers import create_user_and_jwt

    email, uid, token = create_user_and_jwt()
    data = decode_access_token(token)
    assert data.user_id == uid
    assert data.email == email


@pytest.mark.unit
def test_decode_rejects_non_hs256_algorithm():
    """decode_access_token must not accept tokens signed with a different alg header."""
    settings = get_settings()
    uid = uuid.uuid4()
    token = jwt.encode(
        {
            "user_id": str(uid),
            "email": "a@b.com",
            "exp": 9999999999,
            "iat": 1000000000,
        },
        settings.jwt_secret_key,
        algorithm="HS512",
    )
    with pytest.raises(Exception):
        decode_access_token(token)


@pytest.mark.unit
def test_decode_rejects_wrong_signature():
    settings = get_settings()
    other_secret = "a-different-secret-key-32chars!!"
    uid = uuid.uuid4()
    bad = jwt.encode(
        {
            "user_id": str(uid),
            "email": "x@y.com",
            "exp": 9999999999,
            "iat": 1000000000,
        },
        other_secret,
        algorithm="HS256",
    )
    with pytest.raises(Exception):
        decode_access_token(bad)


@pytest.mark.security
def test_auth_me_requires_valid_jwt(client: TestClient, jwt_token: str):
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {jwt_token}"})
    assert r.status_code == 200
    assert "email" in r.json()


@pytest.mark.security
def test_auth_me_rejects_missing_header(client: TestClient):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


# --- HttpOnly session cookie -------------------------------------------------------

def _cookie_name() -> str:
    return get_settings().session_cookie_name


@pytest.mark.security
def test_session_cookie_authenticates_get(client: TestClient, jwt_token: str):
    client.cookies.set(_cookie_name(), jwt_token)
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert "email" in r.json()


@pytest.mark.security
def test_session_cookie_unsafe_method_requires_csrf_header(client: TestClient, jwt_token: str):
    client.cookies.set(_cookie_name(), jwt_token)
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 403
    assert "X-Requested-With" in r.json()["detail"]


@pytest.mark.security
def test_session_cookie_unsafe_method_rejects_foreign_origin(client: TestClient, jwt_token: str):
    client.cookies.set(_cookie_name(), jwt_token)
    r = client.post(
        "/api/v1/auth/refresh",
        headers={"X-Requested-With": "XMLHttpRequest", "Origin": "https://evil.example"},
    )
    assert r.status_code == 403


@pytest.mark.security
def test_session_cookie_unsafe_method_allowed_with_csrf_header(client: TestClient, jwt_token: str):
    client.cookies.set(_cookie_name(), jwt_token)
    r = client.post(
        "/api/v1/auth/refresh",
        headers={"X-Requested-With": "XMLHttpRequest", "Origin": "http://localhost:3000"},
    )
    assert r.status_code == 200
    set_cookie = r.headers.get("set-cookie", "")
    assert _cookie_name() in set_cookie
    assert "httponly" in set_cookie.lower()


@pytest.mark.security
def test_bearer_header_does_not_require_csrf_header(client: TestClient, jwt_token: str):
    r = client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {jwt_token}"})
    assert r.status_code == 200


@pytest.mark.security
def test_logout_clears_cookie(client: TestClient, jwt_token: str):
    client.cookies.set(_cookie_name(), jwt_token)
    r = client.post("/api/v1/auth/logout", headers={"X-Requested-With": "XMLHttpRequest"})
    assert r.status_code == 204
    set_cookie = r.headers.get("set-cookie", "")
    assert _cookie_name() in set_cookie
    assert 'max-age=0' in set_cookie.lower() or "expires=" in set_cookie.lower()


@pytest.mark.security
def test_invalid_session_cookie_rejected(client: TestClient):
    client.cookies.set(_cookie_name(), "not.a.jwt")
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


@pytest.mark.security
def test_auth_me_rejects_expired_token(client: TestClient, expired_jwt_token: str):
    r = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_jwt_token}"},
    )
    assert r.status_code == 401


@pytest.mark.security
def test_auth_me_rejects_malformed_token(client: TestClient):
    r = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not.a.valid.jwt.structure"},
    )
    assert r.status_code == 401
