"""
Tests for authentication endpoints
"""
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_signup_success():
    """Test successful user signup"""
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "test@example.com",
            "password": "testpassword123"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert "token" in data
    assert "user" in data
    assert data["user"]["email"] == "test@example.com"
    assert data["token_type"] == "bearer"


def test_signup_duplicate_email():
    """Test signup with duplicate email"""
    # First signup
    client.post(
        "/api/v1/auth/signup",
        json={
            "email": "duplicate@example.com",
            "password": "testpassword123"
        }
    )
    
    # Try to signup again with same email
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "duplicate@example.com",
            "password": "anotherpassword"
        }
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


def test_signup_short_password():
    """Test signup with password too short"""
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "short@example.com",
            "password": "short"
        }
    )
    assert response.status_code == 422  # Validation error


def test_login_success():
    """Test successful login"""
    # First create a user
    client.post(
        "/api/v1/auth/signup",
        json={
            "email": "login@example.com",
            "password": "testpassword123"
        }
    )
    
    # Now login
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "login@example.com",
            "password": "testpassword123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["user"]["email"] == "login@example.com"


def test_login_wrong_password():
    """Test login with wrong password"""
    # Create user
    client.post(
        "/api/v1/auth/signup",
        json={
            "email": "wrongpass@example.com",
            "password": "correctpassword"
        }
    )
    
    # Try to login with wrong password
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "wrongpass@example.com",
            "password": "wrongpassword"
        }
    )
    assert response.status_code == 401


def test_login_nonexistent_user():
    """Test login with non-existent user"""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "anypassword"
        }
    )
    assert response.status_code == 401


def test_get_current_user():
    """Test getting current user info with valid token"""
    # Signup to get token
    signup_response = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "currentuser@example.com",
            "password": "testpassword123"
        }
    )
    token = signup_response.json()["token"]
    
    # Get current user
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "currentuser@example.com"


def test_get_current_user_no_token():
    """Test getting current user without token"""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 403  # No credentials


def test_get_current_user_invalid_token():
    """Test getting current user with invalid token"""
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401
