"""
Tests for provider API key management
"""
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def get_auth_token():
    """Helper to create a user and get auth token"""
    import random
    email = f"test{random.randint(1000, 9999)}@example.com"
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "testpassword123"
        }
    )
    return response.json()["token"]


def test_list_supported_providers():
    """Test listing supported providers (public endpoint)"""
    response = client.get("/api/v1/providers/supported")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    assert len(data["providers"]) >= 2  # At least OpenAI and Anthropic
    
    # Check provider structure
    provider = data["providers"][0]
    assert "id" in provider
    assert "name" in provider
    assert "key_format" in provider


def test_list_provider_keys_no_auth():
    """Test listing keys without authentication"""
    response = client.get("/api/v1/providers/keys")
    assert response.status_code == 403


def test_list_provider_keys_empty():
    """Test listing keys for new user (should be empty)"""
    token = get_auth_token()
    response = client.get(
        "/api/v1/providers/keys",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["keys"] == []


def test_set_openai_key():
    """Test setting OpenAI API key"""
    token = get_auth_token()
    response = client.put(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"},
        json={"api_key": "sk-test1234567890abcdefghijklmnopqrstuvwxyz"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "openai"
    assert data["status"] == "active"
    assert "sk-****" in data["masked_key"]
    assert len(data["last_4"]) == 4


def test_set_anthropic_key():
    """Test setting Anthropic API key"""
    token = get_auth_token()
    response = client.put(
        "/api/v1/providers/keys/anthropic",
        headers={"Authorization": f"Bearer {token}"},
        json={"api_key": "sk-ant-test1234567890abcdefghijklmnopqrstuvwxyz"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "anthropic"
    assert data["status"] == "active"


def test_set_invalid_key_format():
    """Test setting key with invalid format"""
    token = get_auth_token()
    response = client.put(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"},
        json={"api_key": "invalid-key"}
    )
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()


def test_update_existing_key():
    """Test updating an existing key"""
    token = get_auth_token()
    
    # Set initial key
    client.put(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"},
        json={"api_key": "sk-test1111111111111111111111111111111111"}
    )
    
    # Update with new key
    response = client.put(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"},
        json={"api_key": "sk-test2222222222222222222222222222222222"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["last_4"] == "2222"


def test_get_specific_provider_key():
    """Test getting a specific provider key"""
    token = get_auth_token()
    
    # Set a key
    client.put(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"},
        json={"api_key": "sk-test3333333333333333333333333333333333"}
    )
    
    # Get the key
    response = client.get(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "openai"
    assert data["last_4"] == "3333"


def test_get_nonexistent_provider_key():
    """Test getting a provider key that doesn't exist"""
    token = get_auth_token()
    response = client.get(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


def test_delete_provider_key():
    """Test deleting a provider key"""
    token = get_auth_token()
    
    # Set a key
    client.put(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"},
        json={"api_key": "sk-test4444444444444444444444444444444444"}
    )
    
    # Delete the key
    response = client.delete(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 204
    
    # Verify it's gone
    response = client.get(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


def test_delete_nonexistent_key():
    """Test deleting a key that doesn't exist"""
    token = get_auth_token()
    response = client.delete(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


def test_user_isolation():
    """Test that users can only see their own keys"""
    token1 = get_auth_token()
    token2 = get_auth_token()
    
    # User 1 sets a key
    client.put(
        "/api/v1/providers/keys/openai",
        headers={"Authorization": f"Bearer {token1}"},
        json={"api_key": "sk-user1111111111111111111111111111111111"}
    )
    
    # User 2 should not see user 1's key
    response = client.get(
        "/api/v1/providers/keys",
        headers={"Authorization": f"Bearer {token2}"}
    )
    assert response.status_code == 200
    assert response.json()["keys"] == []
