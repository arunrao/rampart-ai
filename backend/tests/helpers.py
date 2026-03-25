"""Shared test helpers (importable from test modules without circular conftest imports)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Tuple
from uuid import UUID

from sqlalchemy import text


def create_user_and_jwt(
    email: str | None = None,
    password: str = "testpassword123",
) -> Tuple[str, UUID, str]:
    from api.db import get_conn
    from api.routes.auth import hash_password, create_access_token

    uid = uuid.uuid4()
    email = email or f"user_{uid.hex[:10]}@example.com"
    ph = hash_password(password)
    now = datetime.utcnow()
    with get_conn() as conn:
        conn.execute(
            text(
                """
                INSERT INTO users (id, email, password_hash, created_at, updated_at, is_active)
                VALUES (:id, :email, :ph, :ca, :ua, 1)
                """
            ),
            {"id": str(uid), "email": email, "ph": ph, "ca": now, "ua": now},
        )
        conn.commit()
    token = create_access_token(uid, email)
    return email, uid, token
