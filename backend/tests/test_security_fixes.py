"""
Regression tests for the security review fixes: tenant isolation, ReDoS guard,
JWT secret validation, API key lookup/permissions/rate limits, OAuth state and
client-IP handling.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from tests.helpers import create_user_and_jwt


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def two_users():
    _, uid_a, tok_a = create_user_and_jwt()
    _, uid_b, tok_b = create_user_and_jwt()
    return (uid_a, tok_a), (uid_b, tok_b)


def _insert_api_key(user_id, permissions, per_minute=60, per_hour=1000) -> str:
    """Insert a Rampart API key directly."""
    from api.db import get_session
    from api.models import RampartApiKey
    from api.routes.rampart_keys import generate_rampart_api_key, get_key_preview

    full_key, prefix, key_hash = generate_rampart_api_key()
    with get_session() as s:
        s.add(RampartApiKey(
            user_id=user_id, key_name="test", key_prefix=prefix, key_hash=key_hash,
            key_preview=get_key_preview(full_key), permissions=list(permissions),
            rate_limit_per_minute=per_minute, rate_limit_per_hour=per_hour, is_active=True,
        ))
    return full_key


# ---------------------------------------------------------------------------
# C1: content-filter defaults are per user
# ---------------------------------------------------------------------------

def test_filter_defaults_are_scoped_per_user(client: TestClient, two_users):
    (_, tok_a), (_, tok_b) = two_users
    r = client.put(
        "/api/v1/policies/defaults/content-filter",
        json={"redact": True, "toxicity_threshold": 0.99},
        headers=_headers(tok_a),
    )
    assert r.status_code == 200, r.text

    mine = client.get("/api/v1/policies/defaults/content-filter", headers=_headers(tok_a)).json()
    theirs = client.get("/api/v1/policies/defaults/content-filter", headers=_headers(tok_b)).json()
    assert mine["toxicity_threshold"] == 0.99
    assert theirs["toxicity_threshold"] is None
    assert theirs["redact"] is None


def test_filter_defaults_reject_invalid_regex(client: TestClient, auth_headers: dict):
    r = client.put(
        "/api/v1/policies/defaults/content-filter",
        json={"custom_pii_patterns": {"bad": "(unclosed"}},
        headers=auth_headers,
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# C2: incidents, filter results and traces are isolated between users
# ---------------------------------------------------------------------------

def test_incidents_are_isolated(client: TestClient, two_users):
    from api.routes import security as sec

    (uid_a, _), (_, tok_b) = two_users
    incident_id = uuid.uuid4()
    sec.security_incidents[incident_id] = sec.SecurityIncident(
        id=incident_id,
        threat_type=sec.ThreatType.PROMPT_INJECTION,
        severity=sec.SeverityLevel.HIGH,
        content_preview="user A's private prompt",
        trace_id=None,
        user_id=str(uid_a),
        detected_at=datetime.utcnow(),
        status="open",
        metadata=None,
    )

    listed = client.get("/api/v1/security/incidents", headers=_headers(tok_b)).json()
    assert all(i["id"] != str(incident_id) for i in listed)
    assert client.get(f"/api/v1/security/incidents/{incident_id}", headers=_headers(tok_b)).status_code == 404
    r = client.patch(
        f"/api/v1/security/incidents/{incident_id}/status",
        params={"status": "resolved"},
        headers=_headers(tok_b),
    )
    assert r.status_code == 404
    assert sec.security_incidents[incident_id].status == "open"


def test_filter_results_are_isolated(client: TestClient, two_users):
    import api.routes.content_filter as cf

    (uid_a, tok_a), (_, tok_b) = two_users
    result_id = uuid.uuid4()
    cf.filter_results[result_id] = (
        str(uid_a),
        cf.ContentFilterResponse(
            id=result_id,
            original_content="secret",
            is_safe=True,
            filters_applied=[],
            analyzed_at=datetime.utcnow(),
            processing_time_ms=1.0,
        ),
    )
    assert client.get(f"/api/v1/filter/results/{result_id}", headers=_headers(tok_b)).status_code == 404
    assert client.get(f"/api/v1/filter/results/{result_id}", headers=_headers(tok_a)).status_code == 200


def test_cannot_add_span_to_another_users_trace(client: TestClient, two_users):
    (_, tok_a), (_, tok_b) = two_users
    trace = client.post("/api/v1/traces", json={"name": "a-trace"}, headers=_headers(tok_a))
    assert trace.status_code == 201, trace.text
    r = client.post(
        "/api/v1/spans",
        json={"trace_id": trace.json()["id"], "name": "injected", "span_type": "llm"},
        headers=_headers(tok_b),
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# C3: user-supplied regex cannot ReDoS the server
# ---------------------------------------------------------------------------

def test_redos_pattern_on_filter_is_bounded(client: TestClient, auth_headers):
    body = {
        "content": "a" * 5000 + "!",
        "filters": ["pii"],
        "custom_pii_patterns": {"evil": "(a+)+$"},
    }
    start = time.time()
    r = client.post("/api/v1/filter", json=body, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert time.time() - start < 10


def test_public_demo_disabled_by_default(client: TestClient):
    r = client.post("/api/v1/filter/demo", json={"content": "hi"})
    assert r.status_code == 404


def test_custom_pattern_limits_enforced(client: TestClient):
    too_many = {f"p{i}": "x" for i in range(50)}
    r = client.post("/api/v1/filter/demo", json={"content": "hi", "custom_pii_patterns": too_many})
    assert r.status_code == 422
    r = client.post("/api/v1/filter/demo", json={"content": "hi", "custom_pii_patterns": {"bad": "("}})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# H1: weak/missing JWT secret is refused
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("secret", ["", "short-secret"])
def test_settings_reject_weak_jwt_secret(secret):
    from api.config import Settings

    with pytest.raises(ValueError):
        Settings(jwt_secret_key=secret)


def test_settings_reject_placeholder_secret_in_production():
    from api.config import Settings

    with pytest.raises(ValueError):
        Settings(
            jwt_secret_key="dev-jwt-secret-key-change-in-production-min-32",
            environment="production",
        )


# ---------------------------------------------------------------------------
# H2/H5: API key lookup, permissions and per-key rate limits
# ---------------------------------------------------------------------------

def test_api_key_permissions_enforced(client: TestClient):
    _, uid, _ = create_user_and_jwt()
    key = _insert_api_key(uid, ["filter:pii"])

    r = client.post(
        "/api/v1/security/analyze",
        json={"content": "hello", "context_type": "output"},
        headers=_headers(key),
    )
    assert r.status_code == 403

    r = client.post("/api/v1/filter", json={"content": "hello", "filters": ["pii"]}, headers=_headers(key))
    assert r.status_code == 200, r.text


def test_api_key_rate_limit_enforced(client: TestClient):
    _, uid, _ = create_user_and_jwt()
    key = _insert_api_key(uid, ["filter:pii"], per_minute=1)
    body = {"content": "hello", "filters": ["pii"]}
    assert client.post("/api/v1/filter", json=body, headers=_headers(key)).status_code == 200
    assert client.post("/api/v1/filter", json=body, headers=_headers(key)).status_code == 429


def test_unknown_api_key_skips_bcrypt(client: TestClient, monkeypatch):
    import api.routes.rampart_keys as rk

    calls = []
    monkeypatch.setattr(rk, "verify_rampart_api_key", lambda *a: calls.append(a) or False)
    r = client.post(
        "/api/v1/filter",
        json={"content": "hello", "filters": ["pii"]},
        headers=_headers("rmp_live_" + "x" * 43),
    )
    assert r.status_code == 401
    assert calls == []


def test_deactivated_user_jwt_rejected(client: TestClient):
    from api.db import get_session
    from api.models import User

    _, uid, token = create_user_and_jwt()
    with get_session() as s:
        user = s.get(User, uid)
        assert user is not None
        user.is_active = False
    assert client.get("/api/v1/auth/me", headers=_headers(token)).status_code == 401


# ---------------------------------------------------------------------------
# H3: X-Forwarded-For only trusted for configured proxy hops
# ---------------------------------------------------------------------------

def test_client_ip_ignores_spoofed_forwarded_for(monkeypatch):
    from starlette.requests import Request

    from api.config import get_settings
    from api.middleware.security import get_client_ip

    def make_request(xff: str) -> Request:
        return Request({
            "type": "http",
            "headers": [(b"x-forwarded-for", xff.encode())],
            "client": ("10.0.0.5", 1234),
        })

    settings = get_settings()
    monkeypatch.setattr(settings, "trusted_proxy_count", 0)
    assert get_client_ip(make_request("1.2.3.4")) == "10.0.0.5"

    monkeypatch.setattr(settings, "trusted_proxy_count", 1)
    # Client-supplied "1.2.3.4" is ignored; the ALB-appended address is used
    assert get_client_ip(make_request("1.2.3.4, 203.0.113.9")) == "203.0.113.9"


# ---------------------------------------------------------------------------
# H4: OAuth callback requires matching state
# ---------------------------------------------------------------------------

def test_oauth_callback_rejects_missing_state(client: TestClient, monkeypatch):
    import api.routes.auth as auth

    monkeypatch.setattr(auth.settings, "google_client_id", "cid")
    monkeypatch.setattr(auth.settings, "google_client_secret", "csecret")
    r = client.get("/api/v1/auth/callback/google", params={"code": "abc", "state": "forged"})
    assert r.status_code == 400
