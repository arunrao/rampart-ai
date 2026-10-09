"""
Authentication endpoints - signup, login, JWT management
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Tuple
from datetime import datetime, timedelta
from uuid import UUID
import hmac
import secrets
import jwt
import bcrypt
import httpx
from urllib.parse import urlencode, urlsplit

from api.config import get_settings
from api.db import get_conn
from sqlalchemy import text

router = APIRouter()
# auto_error=False: a missing header is fine when the session cookie is present
security = HTTPBearer(auto_error=False)
settings = get_settings()

# Cookie carrying the OAuth `state` value between /google/login and the callback (CSRF guard)
OAUTH_STATE_COOKIE = "rampart_oauth_state"
OAUTH_STATE_MAX_AGE_SECONDS = 600

# Outbound calls to Google during the OAuth exchange
OAUTH_HTTP_TIMEOUT = httpx.Timeout(10.0)

# Custom header the dashboard must send on cookie-authenticated requests. Browsers only
# attach it after a CORS preflight, so a cross-site form/script cannot forge it (CSRF guard).
CSRF_HEADER = "X-Requested-With"
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _cookie_secure() -> bool:
    return settings.frontend_url.startswith("https://") or settings.google_redirect_uri.startswith("https://")


def set_session_cookie(response: Response, token: str) -> None:
    """Attach the dashboard session (JWT) as an HttpOnly cookie."""
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=_cookie_secure(),
        samesite=settings.session_cookie_samesite,
        domain=settings.session_cookie_domain or None,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        settings.session_cookie_name,
        domain=settings.session_cookie_domain or None,
        path="/",
    )


def _allowed_origins() -> set:
    origins = {o.strip().rstrip("/") for o in settings.cors_origins.split(",") if o.strip()}
    origins.add(settings.frontend_url.rstrip("/"))
    return origins


def enforce_csrf(request: Request) -> None:
    """
    For cookie-authenticated state-changing requests require the custom header and,
    when the browser supplies Origin/Referer, that it matches an allowed dashboard origin.
    """
    if request.method not in _UNSAFE_METHODS:
        return
    if request.headers.get(CSRF_HEADER, "").lower() != "xmlhttprequest":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing {CSRF_HEADER} header on cookie-authenticated request",
        )
    origin = request.headers.get("Origin")
    if not origin:
        referer = request.headers.get("Referer")
        if referer:
            parts = urlsplit(referer)
            origin = f"{parts.scheme}://{parts.netloc}"
    if origin and origin.rstrip("/") not in _allowed_origins():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin not allowed")


def extract_token(
    request: Request, credentials: Optional[HTTPAuthorizationCredentials]
) -> Tuple[str, bool]:
    """
    Return (token, from_cookie). Bearer header wins (API clients / SDKs); otherwise fall
    back to the HttpOnly session cookie, which is subject to the CSRF check.
    """
    if credentials and credentials.scheme.lower() == "bearer" and credentials.credentials:
        return credentials.credentials, False
    cookie = request.cookies.get(settings.session_cookie_name)
    if cookie:
        enforce_csrf(request)
        return cookie, True
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


# Email/password auth removed - using Google OAuth only


class UserResponse(BaseModel):
    """User information response"""
    id: UUID
    email: str
    created_at: datetime
    is_active: bool
    is_super_admin: bool = False


def is_super_admin_email(email: str) -> bool:
    """True if the email is listed in the SUPER_ADMIN_EMAILS setting (case-insensitive)."""
    allowed = {e.strip().lower() for e in get_settings().super_admin_emails.split(",") if e.strip()}
    return bool(allowed) and email.lower() in allowed


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


def _ensure_user_active(user_id: UUID) -> None:
    """Reject tokens for users that no longer exist or have been deactivated."""
    with get_conn() as conn:
        row = conn.execute(
            text("SELECT is_active FROM users WHERE id = :user_id"),
            {"user_id": str(user_id)},
        ).fetchone()
    if not row or not row[0]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive or does not exist"
        )


def decode_access_token(token: str) -> TokenData:
    """Decode and validate a JWT access token"""
    try:
        # Hardcode algorithm to prevent "none" algorithm attack
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        user_id = UUID(payload.get("user_id"))
        email = payload.get("email")
        exp_ts = payload.get("exp")
        if not user_id or not email or exp_ts is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        _ensure_user_active(user_id)
        return TokenData(user_id=user_id, email=email, exp=datetime.fromtimestamp(exp_ts))
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> TokenData:
    """
    Dependency to get the current authenticated user from a JWT, supplied either as
    ``Authorization: Bearer`` or as the HttpOnly session cookie set by the OAuth callback.
    Use this in protected endpoints: user = Depends(get_current_user)
    """
    token, _ = extract_token(request, credentials)
    user = decode_access_token(token)
    # Picked up by AuditLogMiddleware so audit rows carry the acting user
    request.state.user_id = str(user.user_id)
    return user


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
            {"user_id": str(current_user.user_id)}
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
            is_active=result[3],
            is_super_admin=is_super_admin_email(result[1]),
        )


@router.post("/auth/refresh", response_model=AuthResponse)
async def refresh_token(response: Response, current_user: TokenData = Depends(get_current_user)):
    """
    Refresh JWT token.
    Requires valid (not expired) token. Also rotates the session cookie.
    """
    # Get fresh user data
    with get_conn() as conn:
        result = conn.execute(
            text("""
                SELECT id, email, created_at, is_active
                FROM users
                WHERE id = :user_id
            """),
            {"user_id": str(current_user.user_id)}
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
        set_session_cookie(response, token)
        
        return AuthResponse(token=token, user=user)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response):
    """
    End the dashboard session by clearing the HttpOnly cookie.
    Does not require a valid token so a user with an expired session can still clear it;
    the CSRF header is still enforced because this is a cookie-driven state change.
    """
    if request.cookies.get(settings.session_cookie_name):
        enforce_csrf(request)
    clear_session_cookie(response)
    return None


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
    
    # Random state, echoed back by Google and checked against an HttpOnly cookie in the
    # callback so an attacker cannot log a victim into the attacker's account (login CSRF)
    state = secrets.token_urlsafe(32)

    # Build Google OAuth URL
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account",
        "state": state,
    }
    
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    response = RedirectResponse(google_auth_url)
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        max_age=OAUTH_STATE_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.google_redirect_uri.startswith("https://"),
        samesite="lax",
        path=f"{settings.api_prefix}/auth",
    )
    return response


@router.get("/auth/callback/google", response_model=AuthResponse)
async def google_callback(request: Request, code: str, state: Optional[str] = None):
    """
    Handle Google OAuth callback.
    Exchanges authorization code for user info and creates/logs in user.
    """
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth not configured"
        )

    expected_state = request.cookies.get(OAUTH_STATE_COOKIE)
    if not state or not expected_state or not hmac.compare_digest(state, expected_state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state"
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
    
    async with httpx.AsyncClient(timeout=OAUTH_HTTP_TIMEOUT) as client:
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
        # Email is the account identity (and super-admin key), so it must be verified
        if userinfo.get("verified_email") is not True:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Google account email is not verified"
            )
    
    # Check if user exists, create if not
    with get_conn() as conn:
        existing = conn.execute(
            text("SELECT id, email, created_at, is_active FROM users WHERE email = :email"),
            {"email": email}
        ).fetchone()
        
        if existing:
            if not existing[3]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is inactive"
                )
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
            if user_row is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user"
                )
            user = UserResponse(
                id=user_row[0],
                email=user_row[1],
                created_at=user_row[2],
                is_active=user_row[3]
            )
        
        # Create JWT token
        token = create_access_token(user.id, user.email)
        
        # The session lives in an HttpOnly cookie, so the token never touches the URL,
        # browser history, or JavaScript-accessible storage (XSS cannot read it).
        response = RedirectResponse(f"{settings.frontend_url}/auth/callback")
        set_session_cookie(response, token)
        response.delete_cookie(OAUTH_STATE_COOKIE, path=f"{settings.api_prefix}/auth")
        return response
