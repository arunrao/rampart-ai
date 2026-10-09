"""Provider keys written via ``api.routes.api_keys`` must decrypt via ``api.routes.providers``.

Both routes write to the same ``provider_keys.key_encrypted`` column and the LLM proxy
reads through ``providers.get_user_provider_key``; a scheme mismatch would make the
proxy silently fall back to the operator's system key.
"""
from __future__ import annotations

import pytest


@pytest.mark.unit
def test_api_keys_route_uses_shared_crypto():
    from api.routes import api_keys as ak
    from api.security import crypto

    secret = "sk-openai-123456789012345678901234567890"
    enc = ak.encrypt_api_key(secret)
    assert ak.decrypt_api_key(enc) == secret
    assert crypto.decrypt_api_key(enc) == secret


@pytest.mark.security
def test_proxy_sees_key_written_by_api_keys_route(client, auth_headers):
    from api.routes.auth import decode_access_token
    from api.routes.providers import get_user_provider_key

    key = "sk-proxy1234567890abcdefghijklmnopqrstuvwxyz"
    r = client.post("/api/v1/api-keys/keys", headers=auth_headers,
                    json={"provider": "openai", "api_key": key})
    assert r.status_code == 200, r.text

    user = decode_access_token(auth_headers["Authorization"].split()[1])
    assert get_user_provider_key(user.user_id, "openai") == key


@pytest.mark.security
def test_undecryptable_key_raises_instead_of_none(client, auth_headers):
    from sqlalchemy import text
    from api.db import get_conn
    from api.routes.auth import decode_access_token
    from api.routes.providers import ProviderKeyDecryptionError, get_user_provider_key

    r = client.put("/api/v1/providers/keys/anthropic", headers=auth_headers,
                   json={"api_key": "sk-ant-abcdefghijklmnopqrstuvwxyz0123456789"})
    assert r.status_code == 200, r.text
    user = decode_access_token(auth_headers["Authorization"].split()[1])

    with get_conn() as conn:
        conn.execute(
            text("UPDATE provider_keys SET key_encrypted = :bad WHERE user_id = :uid AND provider = 'anthropic'"),
            {"bad": "Z0FBQUFBQmdhcmJhZ2U=", "uid": str(user.user_id)},
        )
        conn.commit()

    with pytest.raises(ProviderKeyDecryptionError):
        get_user_provider_key(user.user_id, "anthropic")
