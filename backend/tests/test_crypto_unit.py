"""Unit tests for ``api.security.crypto`` (provider key encryption)."""
from __future__ import annotations

import os

import pytest


@pytest.mark.unit
def test_encrypt_decrypt_roundtrip(monkeypatch):
    monkeypatch.setenv("KEY_ENCRYPTION_SECRET", "unit-test-encryption-secret-32b!")
    from api.security.crypto import decrypt_api_key, encrypt_api_key

    secret = "sk-test1234567890abcdefghijklmnopqrstuvwxyz"
    enc, last4 = encrypt_api_key(secret)
    assert last4 == secret[-4:]
    assert decrypt_api_key(enc) == secret


@pytest.mark.unit
def test_encrypt_requires_non_empty(monkeypatch):
    monkeypatch.setenv("KEY_ENCRYPTION_SECRET", "unit-test-encryption-secret-32b!")
    from api.security.crypto import encrypt_api_key

    with pytest.raises(ValueError):
        encrypt_api_key("")


@pytest.mark.security
def test_encrypt_requires_env_secret(monkeypatch):
    monkeypatch.delenv("KEY_ENCRYPTION_SECRET", raising=False)
    # Force re-import of module-level behavior via fresh function import
    from api.security.crypto import encrypt_api_key

    with pytest.raises(ValueError, match="KEY_ENCRYPTION_SECRET"):
        encrypt_api_key("sk-test1234567890abcdefghijklmnopqrstuvwxyz")


@pytest.mark.unit
def test_validate_api_key_format():
    from api.security.crypto import validate_api_key_format

    assert validate_api_key_format("sk-12345678901234567890", "openai")
    assert not validate_api_key_format("short", "openai")
    assert validate_api_key_format("sk-ant-123456789012345678901234", "anthropic")
    assert not validate_api_key_format("sk-openai-wrong", "anthropic")
