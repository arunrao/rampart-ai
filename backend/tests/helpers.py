"""Shared test helpers (importable from test modules without circular conftest imports)."""
from __future__ import annotations

import uuid
from typing import Tuple
from uuid import UUID


def create_user_and_jwt(
    email: str | None = None,
    password: str = "testpassword123",
) -> Tuple[str, UUID, str]:
    from api.db import get_session
    from api.models import User
    from api.routes.auth import hash_password, create_access_token

    uid = uuid.uuid4()
    email = email or f"user_{uid.hex[:10]}@example.com"
    with get_session() as s:
        s.add(User(id=uid, email=email, password_hash=hash_password(password)))
    token = create_access_token(uid, email)
    return email, uid, token
