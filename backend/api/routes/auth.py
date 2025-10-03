"""
Authentication endpoints - signup, login, JWT management
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime, timedelta
from uuid import UUID
import jwt
import bcrypt

from api.config import get_settings
from api.db import get_conn
from sqlalchemy import text

router = APIRouter()
security = HTTPBearer()
settings = get_settings()


class SignupRequest(BaseModel):
    """User signup request"""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")


class LoginRequest(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


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
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
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
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
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


@router.post("/auth/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(request: SignupRequest):
    """
    Create a new user account.
    
    - **email**: Valid email address
    - **password**: At least 8 characters
    
    Returns JWT token and user information.
    """
    # Check if user already exists
    with get_conn() as conn:
        existing = conn.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": request.email}
        ).fetchone()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password
        password_hash = hash_password(request.password)
        
        # Create user
        result = conn.execute(
            text("""
                INSERT INTO users (email, password_hash, created_at, updated_at)
                VALUES (:email, :password_hash, :now, :now)
                RETURNING id, email, created_at, is_active
            """),
            {
                "email": request.email,
                "password_hash": password_hash,
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
        
        return AuthResponse(token=token, user=user)


@router.post("/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """
    Login with email and password.
    
    Returns JWT token and user information.
    """
    with get_conn() as conn:
        result = conn.execute(
            text("""
                SELECT id, email, password_hash, created_at, is_active
                FROM users
                WHERE email = :email
            """),
            {"email": request.email}
        ).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        user_id, email, password_hash, created_at, is_active = result
        
        # Verify password
        if not verify_password(request.password, password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        if not is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive"
            )
        
        user = UserResponse(
            id=user_id,
            email=email,
            created_at=created_at,
            is_active=is_active
        )
        
        # Create JWT token
        token = create_access_token(user.id, user.email)
        
        return AuthResponse(token=token, user=user)


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
