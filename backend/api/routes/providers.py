"""
Provider API key management endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from enum import Enum
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.routes.auth import get_current_user, TokenData
from api.security.crypto import encrypt_api_key, decrypt_api_key, mask_api_key, validate_api_key_format
from api.db import get_db, get_session
from api.models import ProviderKey

router = APIRouter()
logger = logging.getLogger(__name__)


class ProviderKeyDecryptionError(RuntimeError):
    """A stored provider key exists but cannot be decrypted with the current KEY_ENCRYPTION_SECRET."""

    def __init__(self, provider: str):
        super().__init__(f"Stored {provider} API key could not be decrypted")
        self.provider = provider


class ProviderType(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class ProviderKeyStatus(str, Enum):
    """Provider key status"""
    ACTIVE = "active"
    REVOKED = "revoked"


class SetProviderKeyRequest(BaseModel):
    """Request to set a provider API key"""
    api_key: str = Field(..., min_length=10, description="Provider API key")


class ProviderKeyResponse(BaseModel):
    """Provider key information (masked)"""
    id: UUID
    provider: ProviderType
    masked_key: str
    last_4: str
    status: ProviderKeyStatus
    created_at: datetime
    updated_at: datetime


class ProviderKeysListResponse(BaseModel):
    """List of provider keys"""
    keys: List[ProviderKeyResponse]


def _to_response(key: ProviderKey) -> ProviderKeyResponse:
    return ProviderKeyResponse(
        id=key.id,
        provider=ProviderType(key.provider),
        masked_key=mask_api_key(key.last_4, key.provider),
        last_4=key.last_4,
        status=ProviderKeyStatus(key.status),
        created_at=key.created_at,
        updated_at=key.updated_at,
    )


def _user_key_stmt(user_id: UUID, provider: str):
    return select(ProviderKey).where(ProviderKey.user_id == user_id, ProviderKey.provider == provider)


@router.get("/providers/keys", response_model=ProviderKeysListResponse)
async def list_provider_keys(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all provider API keys for the current user (masked).
    Requires authentication.
    """
    keys = db.scalars(
        select(ProviderKey)
        .where(ProviderKey.user_id == current_user.user_id)
        .order_by(ProviderKey.created_at.desc())
    ).all()
    return ProviderKeysListResponse(keys=[_to_response(k) for k in keys])


@router.get("/providers/keys/{provider}", response_model=ProviderKeyResponse)
async def get_provider_key(
    provider: ProviderType,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a specific provider API key (masked).
    Requires authentication.
    """
    key = db.scalars(_user_key_stmt(current_user.user_id, provider.value)).first()
    if key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {provider.value} key found"
        )
    return _to_response(key)


@router.put("/providers/keys/{provider}", response_model=ProviderKeyResponse, status_code=status.HTTP_200_OK)
async def set_provider_key(
    provider: ProviderType,
    request: SetProviderKeyRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Set or update a provider API key.
    The key is encrypted before storage.
    Requires authentication.
    """
    # Validate key format
    if not validate_api_key_format(request.api_key, provider.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {provider.value} API key format"
        )
    
    # Encrypt the key
    try:
        encrypted_key, last_4 = encrypt_api_key(request.api_key)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to encrypt API key: {str(e)}"
        )
    
    # Store or update in database
    key = db.scalars(_user_key_stmt(current_user.user_id, provider.value)).first()
    if key is None:
        key = ProviderKey(user_id=current_user.user_id, provider=provider.value)
        db.add(key)
    key.key_encrypted = encrypted_key
    key.last_4 = last_4
    key.status = ProviderKeyStatus.ACTIVE.value
    key.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(key)
    return _to_response(key)


@router.delete("/providers/keys/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider_key(
    provider: ProviderType,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete (revoke) a provider API key.
    Requires authentication.
    """
    key = db.scalars(_user_key_stmt(current_user.user_id, provider.value)).first()
    if key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {provider.value} key found"
        )
    db.delete(key)
    db.commit()
    return None


@router.get("/providers/supported")
async def list_supported_providers():
    """
    List all supported LLM providers.
    Public endpoint - no authentication required.
    """
    return {
        "providers": [
            {
                "id": ProviderType.OPENAI.value,
                "name": "OpenAI",
                "description": "OpenAI GPT models (GPT-6 Astra, GPT-6.1 Sol, GPT-6 Luna, etc.)",
                "key_format": "sk-...",
                "docs_url": "https://platform.openai.com/api-keys"
            },
            {
                "id": ProviderType.ANTHROPIC.value,
                "name": "Anthropic",
                "description": "Anthropic Claude models",
                "key_format": "sk-ant-...",
                "docs_url": "https://console.anthropic.com/settings/keys"
            }
        ]
    }


# Internal helper function for LLM proxy integration
def get_user_provider_key(user_id: UUID, provider: str) -> Optional[str]:
    """
    Get decrypted provider API key for a user.
    Returns None if not found.
    Internal use only - not exposed as endpoint.
    """
    with get_session() as db:
        encrypted = db.scalars(
            _user_key_stmt(user_id, provider).where(ProviderKey.status == ProviderKeyStatus.ACTIVE.value)
        ).first()
        key_encrypted = encrypted.key_encrypted if encrypted else None

    if key_encrypted is None:
        return None

    try:
        return decrypt_api_key(key_encrypted)
    except Exception as e:
        # Surface this: a silent None here makes the LLM proxy fall back to the
        # operator's system key, billing the user's traffic to the platform.
        logger.error(
            "Failed to decrypt %s provider key for user %s (KEY_ENCRYPTION_SECRET rotated?): %s",
            provider, user_id, type(e).__name__,
        )
        raise ProviderKeyDecryptionError(provider) from e
