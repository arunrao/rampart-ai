"""
Pytest configuration: isolated SQLite DB, secrets, and auth helpers.

Environment variables are set before any ``api.*`` import during collection.
"""
from __future__ import annotations

import os
import pathlib
import uuid
from datetime import datetime, timedelta

import pytest

from tests.helpers import create_user_and_jwt

_TEST_ROOT = pathlib.Path(__file__).resolve().parent
_TEST_DB_PATH = _TEST_ROOT / ".pytest_rampart.sqlite"


def _ensure_test_env() -> None:
    os.environ.setdefault("SECRET_KEY", "pytest-secret-key-minimum-32-characters!")
    os.environ.setdefault("JWT_SECRET_KEY", "pytest-jwt-secret-key-min-32-chars!!")
    os.environ.setdefault("KEY_ENCRYPTION_SECRET", "pytest-key-encryption-secret-32ch")
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB_PATH}")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
    os.environ.setdefault("ENVIRONMENT", "test")
    os.environ.setdefault("DEBUG", "false")


_ensure_test_env()


def pytest_configure(config: pytest.Config) -> None:
    _ensure_test_env()
    if _TEST_DB_PATH.exists():
        _TEST_DB_PATH.unlink()
    import api.db as db

    db.reset_engine()
    from api.db import init_all_tables

    init_all_tables()


def pytest_unconfigure(config: pytest.Config) -> None:
    try:
        import api.db as db

        db.reset_engine()
    except Exception:
        pass
    if _TEST_DB_PATH.exists():
        _TEST_DB_PATH.unlink(missing_ok=True)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from api.main import app

    return TestClient(app)


@pytest.fixture
def jwt_token() -> str:
    _, _, token = create_user_and_jwt()
    return token


@pytest.fixture
def auth_headers(jwt_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jwt_token}"}


@pytest.fixture
def expired_jwt_token() -> str:
    """JWT signed with correct secret but expired exp claim."""
    import jwt
    from api.config import get_settings

    settings = get_settings()
    uid = uuid.uuid4()
    now = datetime.utcnow()
    payload = {
        "user_id": str(uid),
        "email": "expired@example.com",
        "exp": now - timedelta(minutes=5),
        "iat": now - timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
