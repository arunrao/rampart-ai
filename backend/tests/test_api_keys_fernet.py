"""Fernet-based provider key helpers in ``api.routes.api_keys`` (legacy path)."""
from __future__ import annotations

import pytest


@pytest.mark.unit
def test_encrypt_decrypt_provider_key_fernet():
    from api.routes import api_keys as ak

    ak._fernet_cipher.cache_clear()
    secret = "sk-openai-123456789012345678901234567890"
    enc = ak.encrypt_api_key(secret)
    assert ak.decrypt_api_key(enc) == secret
    ak._fernet_cipher.cache_clear()
