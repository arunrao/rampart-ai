"""Health and root endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_health_ok(client: TestClient):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "healthy"
    assert "services" in body


@pytest.mark.unit
def test_health_ready_live(client: TestClient):
    assert client.get("/api/v1/health/ready").status_code == 200
    assert client.get("/api/v1/health/live").status_code == 200


@pytest.mark.unit
def test_root_json(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    assert "version" in r.json()
