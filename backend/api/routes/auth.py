"""
Authentication endpoints - signup, login, JWT management
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime, timedelta
from uuid import UUID
import jwt
import bcrypt
import httpx
from urllib.parse import urlencode

from api.config import get_settings
from api.db import get_conn
from sqlalchemy import text

router = APIRouter()
security = HTTPBearer()
settings = get_settings()


# Email/password auth removed - using Google OAuth only


class UserResponse(BaseModel):
    """User information response"""
    id: UUID
    email: str
    created_at: datetime
    is_active: bool


class AuthResponse(BaseModel):
    """Authentication response with token"""
    token: str
    user: UserResponse
    token_type: str = "bearer"


class TokenData(BaseModel):
    """JWT token payload"""
    user_id: UUID
    email: str
    exp: datetime


def hash_password(password: str) -> str:
    """Hash a password using bcrypt with secure work factor"""
    # Use work factor of 12 for better security (default is 12, but explicit is better)
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def create_access_token(user_id: UUID, email: str) -> str:
    """Create a JWT access token"""
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "user_id": str(user_id),
        "email": email,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token


def decode_access_token(token: str) -> TokenData:
    """Decode and validate a JWT access token"""
    try:
        # Hardcode algorithm to prevent "none" algorithm attack
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        user_id = UUID(payload.get("user_id"))
        email = payload.get("email")
        exp = datetime.fromtimestamp(payload.get("exp"))
        
        if not user_id or not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        return TokenData(user_id=user_id, email=email, exp=exp)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> TokenData:
    """
    Dependency to get the current authenticated user from JWT token.
    Use this in protected endpoints: user = Depends(get_current_user)
    """
    token = credentials.credentials
    return decode_access_token(token)


# Email/password signup and login removed - using Google OAuth only


@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: TokenData = Depends(get_current_user)):
    """
    Get current user information from JWT token.
    Requires authentication.
    """
    with get_conn() as conn:
        result = conn.execute(
            text("""
                SELECT id, email, created_at, is_active
                FROM users
                WHERE id = :user_id
            """),
            {"user_id": current_user.user_id}
        ).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserResponse(
            id=result[0],
            email=result[1],
            created_at=result[2],
            is_active=result[3]
        )


@router.post("/auth/refresh", response_model=AuthResponse)
async def refresh_token(current_user: TokenData = Depends(get_current_user)):
    """
    Refresh JWT token.
    Requires valid (not expired) token.
    """
    # Get fresh user data
    with get_conn() as conn:
        result = conn.execute(
            text("""
                SELECT id, email, created_at, is_active
                FROM users
                WHERE id = :user_id
            """),
            {"user_id": current_user.user_id}
        ).fetchone()
        
        if not result or not result[3]:  # Check is_active
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive"
            )
        
        user = UserResponse(
            id=result[0],
            email=result[1],
            created_at=result[2],
            is_active=result[3]
        )
        
        # Create new token
        token = create_access_token(user.id, user.email)
        
        return AuthResponse(token=token, user=user)


@router.get("/auth/google/login")
async def google_login():
    """
    Initiate Google OAuth login flow.
    Redirects user to Google's OAuth consent screen.
    """
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth not configured"
        )
    
    # Build Google OAuth URL
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account"
    }
    
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(google_auth_url)


@router.get("/auth/callback/google", response_model=AuthResponse)
async def google_callback(code: str, state: Optional[str] = None):
    """
    Handle Google OAuth callback.
    Exchanges authorization code for user info and creates/logs in user.
    """
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth not configured"
        )
    
    # Exchange code for access token
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code"
    }
    
    async with httpx.AsyncClient() as client:
        # Get access token
        token_response = await client.post(token_url, data=token_data)
        if token_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange code for token"
            )
        
        token_json = token_response.json()
        access_token = token_json.get("access_token")
        
        # Get user info from Google
        userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        userinfo_response = await client.get(
            userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if userinfo_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get user info from Google"
            )
        
        userinfo = userinfo_response.json()
        email = userinfo.get("email")
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not provided by Google"
            )
    
    # Check if user exists, create if not
    with get_conn() as conn:
        existing = conn.execute(
            text("SELECT id, email, created_at, is_active FROM users WHERE email = :email"),
            {"email": email}
        ).fetchone()
        
        if existing:
            # User exists, log them in
            user = UserResponse(
                id=existing[0],
                email=existing[1],
                created_at=existing[2],
                is_active=existing[3]
            )
        else:
            # Create new user (no password needed for OAuth users)
            # Use a random hash as placeholder since password field is required
            placeholder_hash = hash_password(bcrypt.gensalt().decode('utf-8'))
            
            result = conn.execute(
                text("""
                    INSERT INTO users (email, password_hash, created_at, updated_at)
                    VALUES (:email, :password_hash, :now, :now)
                    RETURNING id, email, created_at, is_active
                """),
                {
                    "email": email,
                    "password_hash": placeholder_hash,
                    "now": datetime.utcnow()
                }
            )
            conn.commit()
            
            user_row = result.fetchone()
            user = UserResponse(
                id=user_row[0],
                email=user_row[1],
                created_at=user_row[2],
                is_active=user_row[3]
            )
        
        # Create JWT token
        token = create_access_token(user.id, user.email)
        
        # Redirect to frontend with token
        frontend_url = f"http://localhost:3000/auth/callback?token={token}"
        return RedirectResponse(frontend_url)
