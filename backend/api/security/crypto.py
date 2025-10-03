"""
Cryptographic utilities for secure API key storage
"""
import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Tuple


def get_encryption_key() -> bytes:
    """
    Get or derive the encryption key for API keys.
    In production, use a proper KMS or secrets manager.
    """
    key_secret = os.getenv("KEY_ENCRYPTION_SECRET")
    if not key_secret:
        raise ValueError("KEY_ENCRYPTION_SECRET environment variable not set")
    
    # Derive a 32-byte key using PBKDF2HMAC
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"rampart-key-salt",  # In production, use unique salt per deployment
        iterations=100000,
    )
    return kdf.derive(key_secret.encode())


def encrypt_api_key(plaintext_key: str) -> Tuple[str, str]:
    """
    Encrypt an API key using AES-GCM.
    
    Returns:
        Tuple of (encrypted_base64, last_4_chars)
    """
    if not plaintext_key:
        raise ValueError("API key cannot be empty")
    
    # Get encryption key
    key = get_encryption_key()
    aesgcm = AESGCM(key)
    
    # Generate random nonce (96 bits for GCM)
    nonce = os.urandom(12)
    
    # Encrypt
    ciphertext = aesgcm.encrypt(nonce, plaintext_key.encode(), None)
    
    # Combine nonce + ciphertext and base64 encode
    encrypted = base64.b64encode(nonce + ciphertext).decode('utf-8')
    
    # Extract last 4 characters for display
    last_4 = plaintext_key[-4:] if len(plaintext_key) >= 4 else plaintext_key
    
    return encrypted, last_4


def decrypt_api_key(encrypted_base64: str) -> str:
    """
    Decrypt an API key.
    
    Args:
        encrypted_base64: Base64-encoded nonce+ciphertext
        
    Returns:
        Plaintext API key
    """
    if not encrypted_base64:
        raise ValueError("Encrypted key cannot be empty")
    
    # Get encryption key
    key = get_encryption_key()
    aesgcm = AESGCM(key)
    
    # Decode from base64
    encrypted = base64.b64decode(encrypted_base64)
    
    # Split nonce and ciphertext
    nonce = encrypted[:12]
    ciphertext = encrypted[12:]
    
    # Decrypt
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    
    return plaintext.decode('utf-8')


def mask_api_key(last_4: str, provider: str = "openai") -> str:
    """
    Create a masked display version of an API key.
    
    Args:
        last_4: Last 4 characters of the key
        provider: Provider name (openai, anthropic)
        
    Returns:
        Masked key like "sk-****abcd" or "sk-ant-****abcd"
    """
    if provider == "openai":
        return f"sk-****{last_4}"
    elif provider == "anthropic":
        return f"sk-ant-****{last_4}"
    else:
        return f"****{last_4}"


def validate_api_key_format(api_key: str, provider: str) -> bool:
    """
    Validate API key format for a given provider.
    
    Args:
        api_key: The API key to validate
        provider: Provider name (openai, anthropic)
        
    Returns:
        True if format is valid
    """
    if not api_key:
        return False
    
    if provider == "openai":
        # OpenAI keys start with sk- and are typically 48-51 chars
        return api_key.startswith("sk-") and len(api_key) >= 20
    elif provider == "anthropic":
        # Anthropic keys start with sk-ant- and are typically longer
        return api_key.startswith("sk-ant-") and len(api_key) >= 20
    
    return False
