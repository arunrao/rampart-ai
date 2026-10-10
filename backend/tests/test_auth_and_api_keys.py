"""/auth/me, /auth/refresh, Google OAuth callback (first login creates the user, later logins reuse it)
and the /api-keys provider-key CRUD, all through the ORM-backed routes."""
import uuid
from unittest.mock import patch
from tests.helpers import create_user_and_jwt


def test_api_keys_crud(client, auth_headers):
    r = client.post("/api/v1/api-keys/keys", headers=auth_headers, json={"provider": "openai", "api_key": "sk-" + "a" * 40, "name": "n"})
    assert r.status_code == 200, r.text
    kid = r.json()["id"]
    assert r.json()["key_preview"] == "...aaaa" and r.json()["is_valid"] is True and r.json()["name"] == "n"
    r = client.post("/api/v1/api-keys/keys", headers=auth_headers, json={"provider": "openai", "api_key": "sk-" + "b" * 40})
    assert r.json()["id"] == kid and r.json()["key_preview"] == "...bbbb"  # upsert keeps id
    assert [k["provider"] for k in client.get("/api/v1/api-keys/keys", headers=auth_headers).json()] == ["openai"]
    assert client.get("/api/v1/api-keys/keys/openai", headers=auth_headers).json()["id"] == kid
    assert client.get("/api/v1/api-keys/keys/cohere", headers=auth_headers).status_code == 404
    # another user cannot delete it
    _, _, other = create_user_and_jwt()
    assert client.delete(f"/api/v1/api-keys/keys/{kid}", headers={"Authorization": f"Bearer {other}"}).status_code == 404
    assert client.delete(f"/api/v1/api-keys/keys/{kid}", headers=auth_headers).status_code == 200
    assert client.delete(f"/api/v1/api-keys/keys/{kid}", headers=auth_headers).status_code == 404


def test_auth_me_and_refresh(client, auth_headers):
    me = client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200 and me.json()["is_active"] is True
    r = client.post("/api/v1/auth/refresh", headers=auth_headers)
    assert r.status_code == 200 and r.json()["user"]["id"] == me.json()["id"]


def test_google_callback_creates_then_reuses_user(client):
    from api.routes import auth as a
    from api.db import get_session
    from api.models import User
    from sqlalchemy import select
    email = f"g_{uuid.uuid4().hex[:8]}@example.com"

    class R:
        def __init__(self, code, body): self.status_code, self._b = code, body
        def json(self): return self._b

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **k): return R(200, {"access_token": "t"})
        async def get(self, *a, **k): return R(200, {"email": email, "verified_email": True})

    state = "s" * 32
    with patch.object(a.httpx, "AsyncClient", lambda *a, **k: FakeClient()), \
         patch.object(a.settings, "google_client_id", "cid"), patch.object(a.settings, "google_client_secret", "sec"):
        client.cookies.set(a.OAUTH_STATE_COOKIE, state)
        for _ in range(2):
            r = client.get("/api/v1/auth/callback/google", params={"code": "c", "state": state}, follow_redirects=False)
            assert r.status_code in (302, 307), r.text
            assert a.settings.session_cookie_name in r.cookies
    with get_session() as s:
        users = s.scalars(select(User).where(User.email == email)).all()
        assert len(users) == 1 and users[0].is_active is True
