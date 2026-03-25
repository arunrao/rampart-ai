"""
Tests for provider API key management (Google OAuth + JWT; users seeded in DB).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.helpers import create_user_and_jwt


def _bearer() -> str:
    return create_user_and_jwt()[2]


@pytest.mark.integration
def test_list_supported_providers(client: TestClient):
    response = client.get("/api/v1/providers/supported")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    assert len(data["providers"]) >= 2
    provider = data["providers"][0]
    assert "id" in provider
    assert "name" in provider
    assert "key_format" in provider


@pytest.mark.security
def test_list_provider_keys_no_auth(client: TestClient):
    response = client.get("/api/v1/providers/keys")
    assert response.status_code == 401


@pytest.mark.integration
def test_list_provider_keys_empty(client: TestClient):
    token = _bearer()
    response = client.get(
        "/api/v1/providers/keys",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["keys"] == []


@pytest.mark.integration
def test_set_openai_key(client: TestClient):
    token = _bearer()
    response = client.put(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"},
        json={"api_key": "sk-test1234567890abcdefghijklmnopqrstuvwxyz"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "openai"
    assert data["status"] == "active"
    assert "sk-****" in data["masked_key"]
    assert len(data["last_4"]) == 4


@pytest.mark.integration
def test_set_anthropic_key(client: TestClient):
    token = _bearer()
    response = client.put(
        "/api/v1/providers/keys/anthropic",
        headers={"Authorization": f"Bearer {token}"},
        json={"api_key": "sk-ant-test1234567890abcdefghijklmnopqrstuvwxyz"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "anthropic"
    assert data["status"] == "active"


@pytest.mark.integration
def test_set_invalid_key_format(client: TestClient):
    token = _bearer()
    response = client.put(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"},
        json={"api_key": "invalid-key"},
    )
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()


@pytest.mark.integration
def test_update_existing_key(client: TestClient):
    token = _bearer()
    client.put(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"},
        json={"api_key": "sk-test1111111111111111111111111111111111"},
    )
    response = client.put(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"},
        json={"api_key": "sk-test2222222222222222222222222222222222"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["last_4"] == "2222"


@pytest.mark.integration
def test_get_specific_provider_key(client: TestClient):
    token = _bearer()
    client.put(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"},
        json={"api_key": "sk-test3333333333333333333333333333333333"},
    )
    response = client.get(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "openai"
    assert data["last_4"] == "3333"


@pytest.mark.integration
def test_get_nonexistent_provider_key(client: TestClient):
    token = _bearer()
    response = client.get(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.integration
def test_delete_provider_key(client: TestClient):
    token = _bearer()
    client.put(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"},
        json={"api_key": "sk-test4444444444444444444444444444444444"},
    )
    response = client.delete(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204
    response = client.get(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.integration
def test_delete_nonexistent_key(client: TestClient):
    token = _bearer()
    response = client.delete(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.security
def test_user_isolation(client: TestClient):
    token1 = _bearer()
    token2 = _bearer()
    client.put(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token1}"},
        json={"api_key": "sk-user1111111111111111111111111111111111"},
    )
    response = client.get(
        "/api/v1/providers/keys",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert response.status_code == 200
    assert response.json()["keys"] == []
