"""
API key management endpoints - for OpenAI, Anthropic, etc.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum
from cryptography.fernet import Fernet
import os
import base64

from api.routes.auth import get_current_user, TokenData
from api.db import get_conn
from sqlalchemy import text

router = APIRouter()

# Initialize encryption key
KEY_ENCRYPTION_SECRET = os.getenv("KEY_ENCRYPTION_SECRET", "dev-encryption-key-change-in-production-32-chars")
# Ensure key is 32 bytes for Fernet
encryption_key = base64.urlsafe_b64encode(KEY_ENCRYPTION_SECRET.encode()[:32].ljust(32, b'0'))
cipher = Fernet(encryption_key)


class ProviderType(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    COHERE = "cohere"
    HUGGINGFACE = "huggingface"


class APIKeyCreate(BaseModel):
    """Request to create/update API key"""
    provider: ProviderType
    api_key: str = Field(..., min_length=10)
    name: Optional[str] = None


class APIKeyResponse(BaseModel):
    """API key information (masked)"""
    id: UUID
    provider: ProviderType
    name: Optional[str]
    key_preview: str  # Last 4 characters only
    created_at: datetime
    updated_at: datetime
    is_valid: bool


class APIKeyTest(BaseModel):
    """Test API key validity"""
    provider: ProviderType
    api_key: str


def encrypt_api_key(api_key: str) -> str:
    """Encrypt API key for storage"""
    return cipher.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt API key from storage"""
    return cipher.decrypt(encrypted_key.encode()).decode()


def mask_api_key(api_key: str) -> str:
    """Mask API key, showing only last 4 characters"""
    if len(api_key) <= 4:
        return "****"
    return f"...{api_key[-4:]}"


def validate_api_key_format(provider: ProviderType, api_key: str) -> bool:
    """Validate API key format"""
    if provider == ProviderType.OPENAI:
        return api_key.startswith("sk-") and len(api_key) > 20
    elif provider == ProviderType.ANTHROPIC:
        return api_key.startswith("sk-ant-") and len(api_key) > 20
    elif provider == ProviderType.COHERE:
        return len(api_key) > 20
    elif provider == ProviderType.HUGGINGFACE:
        return api_key.startswith("hf_") and len(api_key) > 20
    return False


@router.post("/keys", response_model=APIKeyResponse)
async def create_api_key(
    request: APIKeyCreate,
    current_user: TokenData = Depends(get_current_user)
):
    """Create or update an API key for a provider"""
    user_id = current_user.user_id
    
    # Validate key format
    if not validate_api_key_format(request.provider, request.api_key):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid API key format for {request.provider.value}"
        )
    
    # Encrypt the API key
    encrypted_key = encrypt_api_key(request.api_key)
    last_4 = request.api_key[-4:] if len(request.api_key) >= 4 else "****"
    now = datetime.utcnow()
    
    with get_conn() as conn:
        # Check if key for this provider already exists
        existing = conn.execute(
            text("""
                SELECT id FROM provider_keys 
                WHERE user_id = :user_id AND provider = :provider
            """),
            {"user_id": user_id, "provider": request.provider.value}
        ).fetchone()
        
        if existing:
            # Update existing key
            conn.execute(
                text("""
                    UPDATE provider_keys 
                    SET key_encrypted = :key_encrypted,
                        last_4 = :last_4,
                        status = 'active',
                        updated_at = :updated_at
                    WHERE user_id = :user_id AND provider = :provider
                """),
                {
                    "key_encrypted": encrypted_key,
                    "last_4": last_4,
                    "updated_at": now,
                    "user_id": user_id,
                    "provider": request.provider.value
                }
            )
            key_id = existing[0]
        else:
            # Create new key
            key_id = uuid4()
            conn.execute(
                text("""
                    INSERT INTO provider_keys 
                    (id, user_id, provider, key_encrypted, last_4, status, created_at, updated_at)
                    VALUES (:id, :user_id, :provider, :key_encrypted, :last_4, 'active', :created_at, :updated_at)
                """),
                {
                    "id": key_id,
                    "user_id": user_id,
                    "provider": request.provider.value,
                    "key_encrypted": encrypted_key,
                    "last_4": last_4,
                    "created_at": now,
                    "updated_at": now
                }
            )
        
        conn.commit()
    
    return APIKeyResponse(
        id=key_id,
        provider=request.provider,
        name=request.name,
        key_preview=mask_api_key(request.api_key),
        created_at=now,
        updated_at=now,
        is_valid=True
    )


@router.get("/keys", response_model=List[APIKeyResponse])
async def list_api_keys(current_user: TokenData = Depends(get_current_user)):
    """List all API keys for the current user"""
    user_id = current_user.user_id
    
    with get_conn() as conn:
        rows = conn.execute(
            text("""
                SELECT id, provider, last_4, status, created_at, updated_at
                FROM provider_keys
                WHERE user_id = :user_id
                ORDER BY created_at DESC
            """),
            {"user_id": user_id}
        ).fetchall()
    
    keys = []
    for row in rows:
        keys.append(APIKeyResponse(
            id=row[0],
            provider=ProviderType(row[1]),
            name=None,  # We don't store name in DB currently
            key_preview=f"...{row[2]}",
            created_at=row[4],
            updated_at=row[5],
            is_valid=row[3] == 'active'
        ))
    
    return keys


@router.get("/keys/{provider}", response_model=APIKeyResponse)
async def get_api_key(
    provider: ProviderType,
    current_user: TokenData = Depends(get_current_user)
):
    """Get API key for a specific provider"""
    user_id = current_user.user_id
    
    with get_conn() as conn:
        row = conn.execute(
            text("""
                SELECT id, provider, last_4, status, created_at, updated_at
                FROM provider_keys
                WHERE user_id = :user_id AND provider = :provider
            """),
            {"user_id": user_id, "provider": provider.value}
        ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail=f"No API key found for {provider.value}")
    
    return APIKeyResponse(
        id=row[0],
        provider=ProviderType(row[1]),
        name=None,
        key_preview=f"...{row[2]}",
        created_at=row[4],
        updated_at=row[5],
        is_valid=row[3] == 'active'
    )


@router.delete("/keys/{key_id}")
async def delete_api_key(
    key_id: UUID,
    current_user: TokenData = Depends(get_current_user)
):
    """Delete an API key"""
    user_id = current_user.user_id
    
    with get_conn() as conn:
        result = conn.execute(
            text("""
                DELETE FROM provider_keys
                WHERE id = :key_id AND user_id = :user_id
            """),
            {"key_id": key_id, "user_id": user_id}
        )
        conn.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="API key not found")
    
    return {"message": "API key deleted successfully", "key_id": key_id}


@router.post("/keys/test")
async def test_api_key(
    request: APIKeyTest,
    current_user: TokenData = Depends(get_current_user)
):
    """Test if an API key is valid by making a simple API call"""
    import httpx
    
    try:
        if request.provider == ProviderType.OPENAI:
            # Test OpenAI key
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {request.api_key}"},
                    timeout=10.0
                )
                if response.status_code == 200:
                    return {
                        "valid": True,
                        "provider": request.provider.value,
                        "message": "API key is valid"
                    }
                else:
                    return {
                        "valid": False,
                        "provider": request.provider.value,
                        "message": f"Invalid API key: {response.status_code}"
                    }
        
        elif request.provider == ProviderType.ANTHROPIC:
            # Test Anthropic key
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": request.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 10,
                        "messages": [{"role": "user", "content": "Hi"}]
                    },
                    timeout=10.0
                )
                if response.status_code in [200, 201]:
                    return {
                        "valid": True,
                        "provider": request.provider.value,
                        "message": "API key is valid"
                    }
                else:
                    return {
                        "valid": False,
                        "provider": request.provider.value,
                        "message": f"Invalid API key: {response.status_code}"
                    }
        
        else:
            # For other providers, just validate format
            is_valid = validate_api_key_format(request.provider, request.api_key)
            return {
                "valid": is_valid,
                "provider": request.provider.value,
                "message": "API key format is valid" if is_valid else "Invalid API key format"
            }
    
    except Exception as e:
        return {
            "valid": False,
            "provider": request.provider.value,
            "message": f"Error testing API key: {str(e)}"
        }


@router.get("/providers")
async def list_providers():
    """List all supported providers"""
    return [
        {
            "id": "openai",
            "name": "OpenAI",
            "description": "GPT-4, GPT-3.5-turbo, and other OpenAI models",
            "key_format": "sk-...",
            "docs_url": "https://platform.openai.com/api-keys"
        },
        {
            "id": "anthropic",
            "name": "Anthropic",
            "description": "Claude 3 models (Opus, Sonnet, Haiku)",
            "key_format": "sk-ant-...",
            "docs_url": "https://console.anthropic.com/settings/keys"
        },
        {
            "id": "cohere",
            "name": "Cohere",
            "description": "Command and other Cohere models",
            "key_format": "...",
            "docs_url": "https://dashboard.cohere.com/api-keys"
        },
        {
            "id": "huggingface",
            "name": "Hugging Face",
            "description": "Access to Hugging Face models",
            "key_format": "hf_...",
            "docs_url": "https://huggingface.co/settings/tokens"
        }
    ]


def get_user_api_key(user_id: str, provider: ProviderType) -> Optional[str]:
    """Helper function to get user's API key for a provider"""
    if user_id not in user_api_keys:
        return None
    
    for key_data in user_api_keys[user_id].values():
        if key_data["provider"] == provider:
            return key_data["api_key"]
    
    return None
