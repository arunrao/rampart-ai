"""Super-admin dashboard endpoints: auth guard, traffic stats, cost rollups."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.helpers import create_user_and_jwt

@pytest.fixture
def admin_headers(monkeypatch) -> dict[str, str]:
    from api.config import get_settings

    email = f"superadmin_{uuid.uuid4().hex[:8]}@example.com"
    # Mixed case + surrounding whitespace to exercise normalisation
    monkeypatch.setattr(get_settings(), "super_admin_emails", f"Ops@Other.com, {email.upper()} ")
    _, _, token = create_user_and_jwt(email=email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seeded_usage():
    """A user with one API key, hourly usage rows and audit log entries."""
    from api.db import get_conn

    email, uid, token = create_user_and_jwt()
    key_id = str(uuid.uuid4())
    now = datetime.utcnow()
    with get_conn() as conn:
        conn.execute(text("""
            INSERT INTO rampart_api_keys (id, user_id, key_name, key_prefix, key_hash, key_preview,
                                          permissions, is_active, created_at, last_used_at)
            VALUES (:id, :uid, 'seed', :prefix, :hash, 'rmp_seed', '[]', 1, :now, :now)
        """), {"id": key_id, "uid": str(uid), "prefix": uuid.uuid4().hex[:8], "hash": uuid.uuid4().hex, "now": now})
        conn.execute(text("""
            INSERT INTO rampart_api_key_usage (api_key_id, endpoint, requests_count, tokens_used, cost_usd, date, hour)
            VALUES (:k, '/filter', 10, 1500, 0.25, :d, :h)
        """), {"k": key_id, "d": now.date().isoformat(), "h": now.hour})
        for i, (status, latency) in enumerate([(200, 10.0), (200, 20.0), (403, 30.0), (401, 40.0)]):
            conn.execute(text("""
                INSERT INTO audit_logs (user_id, endpoint, http_method, ip_address, status_code,
                                        processing_time_ms, event_type, timestamp)
                VALUES (:uid, '/api/v1/filter', 'POST', '127.0.0.1', :status, :lat,
                        :evt, :ts)
            """), {"uid": str(uid), "status": status, "lat": latency,
                   "evt": "auth_failure" if status == 401 else "api_request",
                   "ts": now - timedelta(minutes=i)})
        conn.commit()
    return {"email": email, "user_id": str(uid), "key_id": key_id}


@pytest.mark.unit
def test_admin_requires_super_admin(client: TestClient, auth_headers: dict):
    for path in ("/admin/stats", "/admin/timeseries", "/admin/cost/by-user",
                 "/admin/cost/by-endpoint", "/admin/audit-logs", "/admin/users"):
        assert client.get(f"/api/v1{path}", headers=auth_headers).status_code == 403, path


@pytest.mark.unit
def test_admin_requires_auth(client: TestClient):
    assert client.get("/api/v1/admin/stats").status_code == 401


@pytest.mark.unit
def test_auth_me_reports_super_admin_flag(client: TestClient, auth_headers: dict, admin_headers: dict):
    assert client.get("/api/v1/auth/me", headers=auth_headers).json()["is_super_admin"] is False
    assert client.get("/api/v1/auth/me", headers=admin_headers).json()["is_super_admin"] is True


@pytest.mark.unit
def test_admin_stats_includes_traffic_and_cost(client: TestClient, admin_headers: dict, seeded_usage: dict):
    r = client.get("/api/v1/admin/stats", params={"range": "24h"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["range"] == "24h"
    assert body["users"]["total"] >= 2
    assert body["api_keys"]["total"] >= 1
    req = body["requests"]
    assert req["total"] >= 4
    assert req["errors"] >= 2
    assert req["blocked"] >= 1
    assert req["auth_failures"] >= 1
    assert req["avg_latency_ms"] is not None
    assert req["p95_latency_ms"] is not None
    assert body["usage"]["cost_usd"] >= 0.25
    assert body["usage"]["tokens"] >= 1500
    assert body["usage_all_time"]["cost_usd"] >= body["usage"]["cost_usd"]
    assert any(e["endpoint"] == "/api/v1/filter" for e in body["top_endpoints"])


@pytest.mark.unit
def test_admin_stats_rejects_bad_range(client: TestClient, admin_headers: dict):
    assert client.get("/api/v1/admin/stats", params={"range": "1y"}, headers=admin_headers).status_code == 422


@pytest.mark.unit
def test_admin_timeseries_buckets(client: TestClient, admin_headers: dict, seeded_usage: dict):
    r = client.get("/api/v1/admin/timeseries", params={"range": "24h"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["interval"] == "hour"
    assert 24 <= len(body["points"]) <= 26  # zero-filled hourly buckets
    assert sum(p["requests"] for p in body["points"]) >= 4
    assert sum(p["cost_usd"] for p in body["points"]) >= 0.25

    r = client.get("/api/v1/admin/timeseries", params={"range": "7d"}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["interval"] == "day"
    assert 7 <= len(r.json()["points"]) <= 9


@pytest.mark.unit
def test_admin_cost_by_user(client: TestClient, admin_headers: dict, seeded_usage: dict):
    r = client.get("/api/v1/admin/cost/by-user", params={"range": "7d"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    row = next(u for u in body["users"] if u["email"] == seeded_usage["email"])
    assert row["requests"] == 10
    assert row["tokens"] == 1500
    assert row["cost_usd"] == pytest.approx(0.25)
    assert row["active_keys"] == 1
    assert body["total_cost_usd"] >= 0.25


@pytest.mark.unit
def test_admin_cost_by_endpoint(client: TestClient, admin_headers: dict, seeded_usage: dict):
    r = client.get("/api/v1/admin/cost/by-endpoint", params={"range": "30d"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    row = next(e for e in r.json()["endpoints"] if e["endpoint"] == "/filter")
    assert row["requests"] >= 10 and row["tokens"] >= 1500 and row["unique_keys"] >= 1


@pytest.mark.unit
def test_admin_audit_logs_filters(client: TestClient, admin_headers: dict, seeded_usage: dict):
    r = client.get("/api/v1/admin/audit-logs",
                   params={"user_id": seeded_usage["user_id"], "errors_only": "true"},
                   headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2
    assert all(l["status_code"] >= 400 for l in body["logs"])
    assert all(l["email"] == seeded_usage["email"] for l in body["logs"])

    r = client.get("/api/v1/admin/audit-logs", params={"event_type": "auth_failure", "limit": 5}, headers=admin_headers)
    assert r.status_code == 200
    assert all(l["event_type"] == "auth_failure" for l in r.json()["logs"])


@pytest.mark.unit
def test_admin_users_includes_usage_and_sorting(client: TestClient, admin_headers: dict, seeded_usage: dict):
    r = client.get("/api/v1/admin/users", params={"sort": "cost_usd", "search": seeded_usage["email"]}, headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    u = body["users"][0]
    assert u["api_key_count"] == 1 and u["active_api_key_count"] == 1
    assert u["requests"] == 10 and u["tokens"] == 1500 and u["cost_usd"] == pytest.approx(0.25)

    assert client.get("/api/v1/admin/users", params={"sort": "nope"}, headers=admin_headers).status_code == 422
