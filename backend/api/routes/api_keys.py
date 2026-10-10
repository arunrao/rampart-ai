"""
API key management endpoints - for OpenAI, Anthropic, etc.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from enum import Enum
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.routes.auth import get_current_user, TokenData
from api.security.crypto import encrypt_api_key as _encrypt, decrypt_api_key as _decrypt
from api.db import get_db
from api.models import ProviderKey

router = APIRouter()
logger = logging.getLogger(__name__)


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
    """Encrypt API key for storage (AES-GCM via api.security.crypto — same scheme the LLM proxy decrypts with)"""
    return _encrypt(api_key)[0]


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt API key from storage"""
    return _decrypt(encrypted_key)


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


def _to_response(key: ProviderKey, name: Optional[str] = None) -> APIKeyResponse:
    return APIKeyResponse(
        id=key.id,
        provider=ProviderType(key.provider),
        name=name,  # We don't store name in DB currently
        key_preview=f"...{key.last_4}",
        created_at=key.created_at,
        updated_at=key.updated_at,
        is_valid=key.status == "active",
    )


def _user_key_stmt(user_id: UUID, provider: str):
    return select(ProviderKey).where(ProviderKey.user_id == user_id, ProviderKey.provider == provider)


@router.post("/keys", response_model=APIKeyResponse)
async def create_api_key(
    request: APIKeyCreate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update an API key for a provider"""
    # Validate key format
    if not validate_api_key_format(request.provider, request.api_key):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid API key format for {request.provider.value}"
        )
    
    # Encrypt the API key
    encrypted_key = encrypt_api_key(request.api_key)
    last_4 = request.api_key[-4:] if len(request.api_key) >= 4 else "****"

    key = db.scalars(_user_key_stmt(current_user.user_id, request.provider.value)).first()
    if key is None:
        key = ProviderKey(user_id=current_user.user_id, provider=request.provider.value)
        db.add(key)
    key.key_encrypted = encrypted_key
    key.last_4 = last_4
    key.status = "active"
    key.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(key)
    return _to_response(key, name=request.name)


@router.get("/keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all API keys for the current user"""
    keys = db.scalars(
        select(ProviderKey)
        .where(ProviderKey.user_id == current_user.user_id)
        .order_by(ProviderKey.created_at.desc())
    ).all()
    return [_to_response(k) for k in keys]


@router.get("/keys/{provider}", response_model=APIKeyResponse)
async def get_api_key(
    provider: ProviderType,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get API key for a specific provider"""
    key = db.scalars(_user_key_stmt(current_user.user_id, provider.value)).first()
    if key is None:
        raise HTTPException(status_code=404, detail=f"No API key found for {provider.value}")
    return _to_response(key)


@router.delete("/keys/{key_id}")
async def delete_api_key(
    key_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an API key"""
    key = db.get(ProviderKey, key_id)
    if key is None or key.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="API key not found")
    db.delete(key)
    db.commit()
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
                        "model": "claude-haiku-5-5",
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
    
    except Exception:
        # Don't echo exception text (can include upstream URLs/headers) back to the client
        logger.warning("Provider API key test failed", exc_info=True)
        return {
            "valid": False,
            "provider": request.provider.value,
            "message": "Error testing API key"
        }


@router.get("/providers")
async def list_providers():
    """List all supported providers"""
    return [
        {
            "id": "openai",
            "name": "OpenAI",
            "description": "GPT-6 Astra, GPT-6.1 Sol, GPT-6 Luna, and other OpenAI models",
            "key_format": "sk-...",
            "docs_url": "https://platform.openai.com/api-keys"
        },
        {
            "id": "anthropic",
            "name": "Anthropic",
            "description": "Claude Opus 5.5, Sonnet 5.5, Haiku 5.5, and Fable 5.1",
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
