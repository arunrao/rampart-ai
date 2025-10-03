"""
Provider API key management endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from enum import Enum

from api.routes.auth import get_current_user, TokenData
from api.security.crypto import encrypt_api_key, decrypt_api_key, mask_api_key, validate_api_key_format
from api.db import get_conn
from sqlalchemy import text

router = APIRouter()


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


@router.get("/providers/keys", response_model=ProviderKeysListResponse)
async def list_provider_keys(current_user: TokenData = Depends(get_current_user)):
    """
    List all provider API keys for the current user (masked).
    Requires authentication.
    """
    with get_conn() as conn:
        results = conn.execute(
            text("""
                SELECT id, provider, last_4, status, created_at, updated_at
                FROM provider_keys
                WHERE user_id = :user_id
                ORDER BY created_at DESC
            """),
            {"user_id": current_user.user_id}
        ).fetchall()
        
        keys = []
        for row in results:
            keys.append(ProviderKeyResponse(
                id=row[0],
                provider=ProviderType(row[1]),
                masked_key=mask_api_key(row[2], row[1]),
                last_4=row[2],
                status=ProviderKeyStatus(row[3]),
                created_at=row[4],
                updated_at=row[5]
            ))
        
        return ProviderKeysListResponse(keys=keys)


@router.get("/providers/keys/{provider}", response_model=ProviderKeyResponse)
async def get_provider_key(
    provider: ProviderType,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Get a specific provider API key (masked).
    Requires authentication.
    """
    with get_conn() as conn:
        result = conn.execute(
            text("""
                SELECT id, provider, last_4, status, created_at, updated_at
                FROM provider_keys
                WHERE user_id = :user_id AND provider = :provider
            """),
            {"user_id": current_user.user_id, "provider": provider.value}
        ).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No {provider.value} key found"
            )
        
        return ProviderKeyResponse(
            id=result[0],
            provider=ProviderType(result[1]),
            masked_key=mask_api_key(result[2], result[1]),
            last_4=result[2],
            status=ProviderKeyStatus(result[3]),
            created_at=result[4],
            updated_at=result[5]
        )


@router.put("/providers/keys/{provider}", response_model=ProviderKeyResponse, status_code=status.HTTP_200_OK)
async def set_provider_key(
    provider: ProviderType,
    request: SetProviderKeyRequest,
    current_user: TokenData = Depends(get_current_user)
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
    with get_conn() as conn:
        # Check if key already exists
        existing = conn.execute(
            text("""
                SELECT id FROM provider_keys
                WHERE user_id = :user_id AND provider = :provider
            """),
            {"user_id": current_user.user_id, "provider": provider.value}
        ).fetchone()
        
        if existing:
            # Update existing key
            result = conn.execute(
                text("""
                    UPDATE provider_keys
                    SET key_encrypted = :key_encrypted,
                        last_4 = :last_4,
                        status = 'active',
                        updated_at = :now
                    WHERE user_id = :user_id AND provider = :provider
                    RETURNING id, provider, last_4, status, created_at, updated_at
                """),
                {
                    "user_id": current_user.user_id,
                    "provider": provider.value,
                    "key_encrypted": encrypted_key,
                    "last_4": last_4,
                    "now": datetime.utcnow()
                }
            )
        else:
            # Insert new key
            result = conn.execute(
                text("""
                    INSERT INTO provider_keys (user_id, provider, key_encrypted, last_4, status, created_at, updated_at)
                    VALUES (:user_id, :provider, :key_encrypted, :last_4, 'active', :now, :now)
                    RETURNING id, provider, last_4, status, created_at, updated_at
                """),
                {
                    "user_id": current_user.user_id,
                    "provider": provider.value,
                    "key_encrypted": encrypted_key,
                    "last_4": last_4,
                    "now": datetime.utcnow()
                }
            )
        
        conn.commit()
        row = result.fetchone()
        
        return ProviderKeyResponse(
            id=row[0],
            provider=ProviderType(row[1]),
            masked_key=mask_api_key(row[2], row[1]),
            last_4=row[2],
            status=ProviderKeyStatus(row[3]),
            created_at=row[4],
            updated_at=row[5]
        )


@router.delete("/providers/keys/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider_key(
    provider: ProviderType,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Delete (revoke) a provider API key.
    Requires authentication.
    """
    with get_conn() as conn:
        result = conn.execute(
            text("""
                DELETE FROM provider_keys
                WHERE user_id = :user_id AND provider = :provider
                RETURNING id
            """),
            {"user_id": current_user.user_id, "provider": provider.value}
        )
        conn.commit()
        
        if not result.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No {provider.value} key found"
            )
    
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
                "description": "OpenAI GPT models (GPT-4, GPT-3.5, etc.)",
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
    with get_conn() as conn:
        result = conn.execute(
            text("""
                SELECT key_encrypted
                FROM provider_keys
                WHERE user_id = :user_id AND provider = :provider AND status = 'active'
            """),
            {"user_id": user_id, "provider": provider}
        ).fetchone()
        
        if not result:
            return None
        
        try:
            return decrypt_api_key(result[0])
        except Exception:
            # If decryption fails, return None (key may be corrupted)
            return None
