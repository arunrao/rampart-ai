"""
Security middleware for FastAPI application
"""
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import time
from collections import defaultdict
from typing import Dict, Tuple, Set
import logging

logger = logging.getLogger(__name__)


class APIKeyEnforcementMiddleware(BaseHTTPMiddleware):
    """Enforce API key or JWT authentication on all non-public endpoints"""
    
    # Endpoints that don't require authentication
    PUBLIC_PATHS: Set[str] = {
        "/",
        "/health",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/v1/health",
        "/api/v1/docs",
        "/api/v1/openapi.json",
        "/api/v1/redoc",
        "/api/v1/auth/google/login",
        "/api/v1/auth/callback/google",
    }
    
    # Path prefixes that don't require authentication
    PUBLIC_PREFIXES: Set[str] = {
        "/api/v1/auth/",  # OAuth flow
    }
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # Allow public paths
        if path in self.PUBLIC_PATHS:
            return await call_next(request)
        
        # Allow public prefixes
        for prefix in self.PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)
        
        # Check for Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Authentication required",
                    "detail": "Missing Authorization header. Provide either a Rampart API key (rmp_*) or JWT token in the format: Authorization: Bearer <token>"
                },
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Validate format (should be "Bearer <token>")
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Invalid authentication format",
                    "detail": "Authorization header must be 'Bearer <token>'"
                },
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        token = parts[1]
        
        # Basic validation - token should not be empty and should be reasonable length
        if not token or len(token) < 10:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Invalid token",
                    "detail": "Token appears to be invalid or malformed"
                },
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Token format validation (without actually validating - that happens in endpoints)
        # Rampart API keys start with 'rmp_'
        # JWT tokens are base64 encoded and contain dots
        if not (token.startswith('rmp_') or '.' in token):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Invalid token format",
                    "detail": "Token must be either a Rampart API key (rmp_*) or JWT token"
                },
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Let the request proceed - actual authentication happens in endpoint dependencies
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    def __init__(self, app, cors_origins: str = ""):
        super().__init__(app)
        self.cors_origins = cors_origins
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Build connect-src CSP based on CORS origins
        connect_origins = self.cors_origins if self.cors_origins else "http://localhost:3000"
        
        # Split and format origins properly for CSP
        origin_list = [origin.strip() for origin in connect_origins.split(",")]
        
        # Add websocket variants for local development
        ws_origins = []
        if "localhost" in connect_origins:
            for origin in origin_list:
                ws_origin = origin.replace("http://", "ws://").replace("https://", "wss://")
                if ws_origin != origin:  # Only add if it was actually converted
                    ws_origins.append(ws_origin)
        
        # Combine all origins (including websockets and CDN for source maps)
        all_origins = ["'self'"] + origin_list + ws_origins + ["https://cdn.jsdelivr.net"]
        connect_src = " ".join(all_origins)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            f"connect-src {connect_src}"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware"""
    
    def __init__(self, app, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        # Store: {ip: [(timestamp, count_minute), (timestamp, count_hour)]}
        self.request_counts: Dict[str, Tuple[list, list]] = defaultdict(lambda: ([], []))
        self.cleanup_interval = 60  # Clean up old entries every 60 seconds
        self.last_cleanup = time.time()
        
        # OAuth-specific rate limits (more restrictive)
        self.oauth_requests_per_minute = 10  # Only 10 OAuth attempts per minute
        self.oauth_requests_per_hour = 30    # Only 30 OAuth attempts per hour
        self.oauth_request_counts: Dict[str, Tuple[list, list]] = defaultdict(lambda: ([], []))
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        # Check for forwarded headers (behind proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client
        if request.client:
            return request.client.host
        return "unknown"
    
    def _cleanup_old_entries(self):
        """Remove old entries to prevent memory bloat"""
        current_time = time.time()
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        minute_ago = current_time - 60
        hour_ago = current_time - 3600
        
        # Clean up regular rate limit entries
        for ip in list(self.request_counts.keys()):
            minute_requests, hour_requests = self.request_counts[ip]
            
            # Filter out old requests
            minute_requests[:] = [t for t in minute_requests if t > minute_ago]
            hour_requests[:] = [t for t in hour_requests if t > hour_ago]
            
            # Remove IP if no recent requests
            if not minute_requests and not hour_requests:
                del self.request_counts[ip]
        
        # Clean up OAuth rate limit entries
        for ip in list(self.oauth_request_counts.keys()):
            minute_requests, hour_requests = self.oauth_request_counts[ip]
            
            # Filter out old requests
            minute_requests[:] = [t for t in minute_requests if t > minute_ago]
            hour_requests[:] = [t for t in hour_requests if t > hour_ago]
            
            # Remove IP if no recent requests
            if not minute_requests and not hour_requests:
                del self.oauth_request_counts[ip]
        
        self.last_cleanup = current_time
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health check and metrics endpoints
        if request.url.path in ["/health", "/metrics", "/"]:
            return await call_next(request)
        
        client_ip = self._get_client_ip(request)
        current_time = time.time()
        
        # Cleanup periodically
        self._cleanup_old_entries()
        
        # Check if this is an OAuth endpoint (more restrictive limits)
        is_oauth_endpoint = (
            request.url.path.startswith("/api/v1/auth/google/") or
            request.url.path == "/api/v1/auth/callback/google"
        )
        
        if is_oauth_endpoint:
            # Use OAuth-specific rate limits
            minute_requests, hour_requests = self.oauth_request_counts[client_ip]
            requests_per_minute = self.oauth_requests_per_minute
            requests_per_hour = self.oauth_requests_per_hour
            limit_type = "OAuth"
        else:
            # Use regular rate limits
            minute_requests, hour_requests = self.request_counts[client_ip]
            requests_per_minute = self.requests_per_minute
            requests_per_hour = self.requests_per_hour
            limit_type = "API"
        
        # Remove requests older than 1 minute and 1 hour
        minute_ago = current_time - 60
        hour_ago = current_time - 3600
        
        minute_requests[:] = [t for t in minute_requests if t > minute_ago]
        hour_requests[:] = [t for t in hour_requests if t > hour_ago]
        
        # Check rate limits
        if len(minute_requests) >= requests_per_minute:
            logger.warning(f"{limit_type} rate limit exceeded (per minute) for IP: {client_ip} on {request.url.path}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Maximum {requests_per_minute} {limit_type.lower()} requests per minute allowed. Please try again later."
                },
                headers={"Retry-After": "60"}
            )
        
        if len(hour_requests) >= requests_per_hour:
            logger.warning(f"{limit_type} rate limit exceeded (per hour) for IP: {client_ip} on {request.url.path}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Maximum {requests_per_hour} {limit_type.lower()} requests per hour allowed. Please try again later."
                },
                headers={"Retry-After": "3600"}
            )
        
        # Add current request timestamp
        minute_requests.append(current_time)
        hour_requests.append(current_time)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit-Minute"] = str(requests_per_minute)
        response.headers["X-RateLimit-Remaining-Minute"] = str(
            requests_per_minute - len(minute_requests)
        )
        response.headers["X-RateLimit-Limit-Hour"] = str(requests_per_hour)
        response.headers["X-RateLimit-Remaining-Hour"] = str(
            requests_per_hour - len(hour_requests)
        )
        
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Limit request body size to prevent DoS attacks"""
    
    def __init__(self, app, max_upload_size: int = 10_000_000):  # 10MB default
        super().__init__(app)
        self.max_upload_size = max_upload_size
    
    async def dispatch(self, request: Request, call_next):
        # Check Content-Length header
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_upload_size:
            return JSONResponse(
                status_code=413,
                content={
                    "error": "Request entity too large",
                    "detail": f"Maximum upload size is {self.max_upload_size} bytes"
                }
            )
        
        return await call_next(request)
