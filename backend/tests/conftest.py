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
# Per-process file: a concurrent pytest session deleting a shared DB under our open
# connections surfaces as "attempt to write a readonly database".
_TEST_DB_PATH = _TEST_ROOT / f".pytest_rampart.{os.getpid()}.sqlite"


def _ensure_test_env() -> None:
    os.environ.setdefault("SECRET_KEY", "pytest-secret-key-minimum-32-characters!")
    os.environ.setdefault("JWT_SECRET_KEY", "pytest-jwt-secret-key-min-32-chars!!")
    os.environ.setdefault("KEY_ENCRYPTION_SECRET", "pytest-key-encryption-secret-32ch")
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB_PATH}")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
    os.environ.setdefault("ENVIRONMENT", "test")
    os.environ.setdefault("DEBUG", "false")


_ensure_test_env()


def _reset_database() -> None:
    """Start from an empty schema, then build it the way deploy does (Alembic head)."""
    import api.db as db
    from api.migrate import upgrade_database
    from api.models import Base

    if _TEST_DB_PATH.exists():
        _TEST_DB_PATH.unlink()
    db.reset_engine()
    engine = db.get_engine()
    if engine.dialect.name != "sqlite":
        with engine.begin() as conn:
            Base.metadata.drop_all(conn)
            conn.execute(db.text("DROP TABLE IF EXISTS alembic_version"))
    with engine.connect() as conn:
        upgrade_database(conn)


def pytest_configure(config: pytest.Config) -> None:
    _ensure_test_env()
    _reset_database()


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
    import api.main as main
    from api.main import app

    # Skip the maintenance-mode 503 gate (ML warmup never runs under TestClient)
    main._models_ready = True
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
