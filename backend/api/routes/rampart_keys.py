"""
Rampart API Key Management - for application access (not LLM provider keys)
These are the keys developers use to call Rampart APIs from their applications
"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import secrets
import bcrypt
import hashlib

from api.db import get_conn
from api.routes.auth import get_current_user, TokenData
from sqlalchemy import text

router = APIRouter()


class RampartAPIKeyCreate(BaseModel):
    """Request to create a new Rampart API key"""
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable name for the key")
    permissions: List[str] = Field(
        default=['security:analyze', 'filter:pii', 'llm:chat'],
        description="List of allowed permissions"
    )
    rate_limit_per_minute: Optional[int] = Field(default=60, ge=1, le=10000)
    rate_limit_per_hour: Optional[int] = Field(default=1000, ge=1, le=100000)
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365, description="Optional expiration in days")


class RampartAPIKeyResponse(BaseModel):
    """API key information (without the actual key)"""
    id: UUID
    name: str
    key_preview: str  # e.g., "rmp_live_****abc123"
    permissions: List[str]
    rate_limit_per_minute: int
    rate_limit_per_hour: int
    is_active: bool
    last_used_at: Optional[datetime]
    created_at: datetime
    expires_at: Optional[datetime]
    usage_stats: Optional[dict] = None


class RampartAPIKeyCreateResponse(BaseModel):
    """Response when creating a new API key (includes the actual key once)"""
    key: str  # Full API key - only shown once!
    key_info: RampartAPIKeyResponse


class RampartAPIKeyUsage(BaseModel):
    """Usage statistics for an API key"""
    total_requests: int
    requests_today: int
    tokens_used: int
    cost_usd: float
    top_endpoints: List[dict]


def generate_rampart_api_key() -> tuple[str, str, str]:
    """
    Generate a new Rampart API key
    Returns: (full_key, key_prefix, key_hash)
    """
    # Generate random key parts
    prefix = "rmp_live_"  # Could be rmp_test_ for test keys
    random_part = secrets.token_urlsafe(32)  # 32 bytes = 43 chars base64
    full_key = f"{prefix}{random_part}"
    
    # Create hash for storage (bcrypt for security)
    key_hash = bcrypt.hashpw(full_key.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
    
    return full_key, prefix, key_hash


def verify_rampart_api_key(provided_key: str, stored_hash: str) -> bool:
    """Verify a provided API key against stored hash"""
    return bcrypt.checkpw(provided_key.encode('utf-8'), stored_hash.encode('utf-8'))


def get_key_preview(full_key: str) -> str:
    """Create a preview of the key for display"""
    if len(full_key) < 8:
        return "****"
    return f"{full_key[:12]}****{full_key[-4:]}"


@router.post("/rampart-keys", response_model=RampartAPIKeyCreateResponse)
async def create_rampart_api_key(
    request: RampartAPIKeyCreate,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Create a new Rampart API key for application access.
    This key will be used to authenticate API calls to Rampart endpoints.
    """
    user_id = current_user.user_id
    
    # Validate permissions
    valid_permissions = {
        'security:analyze', 'security:batch', 'filter:pii', 'filter:toxicity',
        'llm:chat', 'llm:stream', 'analytics:read', 'test:run'
    }
    
    invalid_perms = set(request.permissions) - valid_permissions
    if invalid_perms:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid permissions: {list(invalid_perms)}"
        )
    
    # Check user doesn't have too many keys (limit to 10)
    with get_conn() as conn:
        key_count = conn.execute(
            text("SELECT COUNT(*) FROM rampart_api_keys WHERE user_id = :user_id AND is_active = true"),
            {"user_id": user_id}
        ).scalar()
        
        if key_count >= 10:
            raise HTTPException(
                status_code=400,
                detail="Maximum of 10 active API keys allowed per user"
            )
    
    # Generate the key
    full_key, key_prefix, key_hash = generate_rampart_api_key()
    key_preview = get_key_preview(full_key)
    
    # Calculate expiration
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)
    
    # Store in database
    now = datetime.utcnow()
    with get_conn() as conn:
        result = conn.execute(
            text("""
                INSERT INTO rampart_api_keys (
                    user_id, key_name, key_prefix, key_hash, key_preview,
                    permissions, rate_limit_per_minute, rate_limit_per_hour,
                    expires_at, created_at, updated_at
                ) VALUES (
                    :user_id, :key_name, :key_prefix, :key_hash, :key_preview,
                    :permissions, :rate_limit_per_minute, :rate_limit_per_hour,
                    :expires_at, :created_at, :updated_at
                ) RETURNING id
            """),
            {
                "user_id": user_id,
                "key_name": request.name,
                "key_prefix": key_prefix,
                "key_hash": key_hash,
                "key_preview": key_preview,
                "permissions": request.permissions,
                "rate_limit_per_minute": request.rate_limit_per_minute,
                "rate_limit_per_hour": request.rate_limit_per_hour,
                "expires_at": expires_at,
                "created_at": now,
                "updated_at": now
            }
        )
        conn.commit()
        
        key_id = result.scalar()
    
    # Return the key info (full key only shown once!)
    key_info = RampartAPIKeyResponse(
        id=key_id,
        name=request.name,
        key_preview=key_preview,
        permissions=request.permissions,
        rate_limit_per_minute=request.rate_limit_per_minute,
        rate_limit_per_hour=request.rate_limit_per_hour,
        is_active=True,
        last_used_at=None,
        created_at=now,
        expires_at=expires_at
    )
    
    return RampartAPIKeyCreateResponse(
        key=full_key,  # Only time the full key is returned!
        key_info=key_info
    )


@router.get("/rampart-keys", response_model=List[RampartAPIKeyResponse])
async def list_rampart_api_keys(current_user: TokenData = Depends(get_current_user)):
    """List all Rampart API keys for the current user"""
    user_id = current_user.user_id
    
    with get_conn() as conn:
        results = conn.execute(
            text("""
                SELECT 
                    id, key_name, key_preview, permissions,
                    rate_limit_per_minute, rate_limit_per_hour,
                    is_active, last_used_at, created_at, expires_at
                FROM rampart_api_keys 
                WHERE user_id = :user_id 
                ORDER BY created_at DESC
            """),
            {"user_id": user_id}
        ).fetchall()
        
        keys = []
        for row in results:
            # Get usage stats for each key
            usage_stats = conn.execute(
                text("""
                    SELECT 
                        COALESCE(SUM(requests_count), 0) as total_requests,
                        COALESCE(SUM(tokens_used), 0) as tokens_used,
                        COALESCE(SUM(cost_usd), 0) as cost_usd
                    FROM rampart_api_key_usage 
                    WHERE api_key_id = :key_id
                """),
                {"key_id": row[0]}
            ).fetchone()
            
            keys.append(RampartAPIKeyResponse(
                id=row[0],
                name=row[1],
                key_preview=row[2],
                permissions=row[3],
                rate_limit_per_minute=row[4],
                rate_limit_per_hour=row[5],
                is_active=row[6],
                last_used_at=row[7],
                created_at=row[8],
                expires_at=row[9],
                usage_stats={
                    "total_requests": usage_stats[0] if usage_stats else 0,
                    "tokens_used": usage_stats[1] if usage_stats else 0,
                    "cost_usd": float(usage_stats[2]) if usage_stats else 0.0
                }
            ))
        
        return keys


@router.delete("/rampart-keys/{key_id}")
async def delete_rampart_api_key(
    key_id: UUID,
    current_user: TokenData = Depends(get_current_user)
):
    """Delete (deactivate) a Rampart API key"""
    user_id = current_user.user_id
    
    with get_conn() as conn:
        # Verify key belongs to user
        result = conn.execute(
            text("SELECT id FROM rampart_api_keys WHERE id = :key_id AND user_id = :user_id"),
            {"key_id": key_id, "user_id": user_id}
        ).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail="API key not found"
            )
        
        # Soft delete by setting is_active = false
        conn.execute(
            text("""
                UPDATE rampart_api_keys 
                SET is_active = false, updated_at = :now 
                WHERE id = :key_id
            """),
            {"key_id": key_id, "now": datetime.utcnow()}
        )
        conn.commit()
        
        return {"message": "API key deleted successfully"}


@router.get("/rampart-keys/{key_id}/usage", response_model=RampartAPIKeyUsage)
async def get_rampart_api_key_usage(
    key_id: UUID,
    current_user: TokenData = Depends(get_current_user)
):
    """Get detailed usage statistics for a Rampart API key"""
    user_id = current_user.user_id
    
    with get_conn() as conn:
        # Verify key belongs to user
        key_result = conn.execute(
            text("SELECT id FROM rampart_api_keys WHERE id = :key_id AND user_id = :user_id"),
            {"key_id": key_id, "user_id": user_id}
        ).fetchone()
        
        if not key_result:
            raise HTTPException(
                status_code=404,
                detail="API key not found"
            )
        
        # Get overall usage stats
        usage_result = conn.execute(
            text("""
                SELECT 
                    COALESCE(SUM(requests_count), 0) as total_requests,
                    COALESCE(SUM(tokens_used), 0) as tokens_used,
                    COALESCE(SUM(cost_usd), 0) as cost_usd
                FROM rampart_api_key_usage 
                WHERE api_key_id = :key_id
            """),
            {"key_id": key_id}
        ).fetchone()
        
        # Get today's usage
        today_result = conn.execute(
            text("""
                SELECT COALESCE(SUM(requests_count), 0) as requests_today
                FROM rampart_api_key_usage 
                WHERE api_key_id = :key_id AND date = CURRENT_DATE
            """),
            {"key_id": key_id}
        ).fetchone()
        
        # Get top endpoints
        endpoints_result = conn.execute(
            text("""
                SELECT 
                    endpoint,
                    SUM(requests_count) as total_requests,
                    SUM(tokens_used) as total_tokens
                FROM rampart_api_key_usage 
                WHERE api_key_id = :key_id
                GROUP BY endpoint
                ORDER BY total_requests DESC
                LIMIT 10
            """),
            {"key_id": key_id}
        ).fetchall()
        
        top_endpoints = [
            {
                "endpoint": row[0],
                "requests": row[1],
                "tokens": row[2]
            }
            for row in endpoints_result
        ]
        
        return RampartAPIKeyUsage(
            total_requests=usage_result[0] if usage_result else 0,
            requests_today=today_result[0] if today_result else 0,
            tokens_used=usage_result[1] if usage_result else 0,
            cost_usd=float(usage_result[2]) if usage_result else 0.0,
            top_endpoints=top_endpoints
        )


# Authentication dependency for API key access
async def get_current_user_from_api_key(api_key: str) -> tuple[TokenData, UUID]:
    """
    Authenticate user via Rampart API key (not JWT).
    Returns (user_data, api_key_id) for tracking usage.
    """
    if not api_key or not api_key.startswith('rmp_'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format"
        )
    
    with get_conn() as conn:
        # Find matching key
        result = conn.execute(
            text("""
                SELECT 
                    k.id, k.user_id, k.key_hash, k.permissions, k.is_active, k.expires_at,
                    u.email
                FROM rampart_api_keys k
                JOIN users u ON k.user_id = u.id
                WHERE k.key_prefix = :prefix AND k.is_active = true
            """),
            {"prefix": api_key.split('_')[0] + '_' + api_key.split('_')[1] + '_'}  # e.g., 'rmp_live_'
        ).fetchall()
        
        # Check each key hash (there might be multiple with same prefix)
        for row in result:
            key_id, user_id, key_hash, permissions, is_active, expires_at, email = row
            
            if verify_rampart_api_key(api_key, key_hash):
                # Check if expired
                if expires_at and expires_at < datetime.utcnow():
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="API key has expired"
                    )
                
                # Update last_used_at
                conn.execute(
                    text("UPDATE rampart_api_keys SET last_used_at = :now WHERE id = :key_id"),
                    {"now": datetime.utcnow(), "key_id": key_id}
                )
                conn.commit()
                
                # Return user data and key ID
                user_data = TokenData(
                    user_id=user_id,
                    email=email,
                    exp=expires_at or datetime.utcnow() + timedelta(days=365)
                )
                
                return user_data, key_id
        
        # No matching key found
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )


def track_api_key_usage(api_key_id: UUID, endpoint: str, tokens_used: int = 0, cost_usd: float = 0.0):
    """Track usage for an API key"""
    with get_conn() as conn:
        # Insert or update usage record
        conn.execute(
            text("""
                INSERT INTO rampart_api_key_usage (
                    api_key_id, endpoint, requests_count, tokens_used, cost_usd, date, hour
                ) VALUES (
                    :api_key_id, :endpoint, 1, :tokens_used, :cost_usd, CURRENT_DATE, EXTRACT(HOUR FROM CURRENT_TIMESTAMP)
                )
                ON CONFLICT (api_key_id, endpoint, date, hour)
                DO UPDATE SET
                    requests_count = rampart_api_key_usage.requests_count + 1,
                    tokens_used = rampart_api_key_usage.tokens_used + :tokens_used,
                    cost_usd = rampart_api_key_usage.cost_usd + :cost_usd
            """),
            {
                "api_key_id": api_key_id,
                "endpoint": endpoint,
                "tokens_used": tokens_used,
                "cost_usd": cost_usd
            }
        )
        conn.commit()
