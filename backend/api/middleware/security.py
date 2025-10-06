"""
Security middleware for FastAPI application
"""
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import time
from collections import defaultdict
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' http://localhost:3000 http://localhost:3001 ws://localhost:3000 ws://localhost:3001"
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
        
        for ip in list(self.request_counts.keys()):
            minute_requests, hour_requests = self.request_counts[ip]
            
            # Filter out old requests
            minute_requests[:] = [t for t in minute_requests if t > minute_ago]
            hour_requests[:] = [t for t in hour_requests if t > hour_ago]
            
            # Remove IP if no recent requests
            if not minute_requests and not hour_requests:
                del self.request_counts[ip]
        
        self.last_cleanup = current_time
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health check and metrics endpoints
        if request.url.path in ["/health", "/metrics", "/"]:
            return await call_next(request)
        
        client_ip = self._get_client_ip(request)
        current_time = time.time()
        
        # Cleanup periodically
        self._cleanup_old_entries()
        
        minute_requests, hour_requests = self.request_counts[client_ip]
        
        # Remove requests older than 1 minute and 1 hour
        minute_ago = current_time - 60
        hour_ago = current_time - 3600
        
        minute_requests[:] = [t for t in minute_requests if t > minute_ago]
        hour_requests[:] = [t for t in hour_requests if t > hour_ago]
        
        # Check rate limits
        if len(minute_requests) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded (per minute) for IP: {client_ip}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Maximum {self.requests_per_minute} requests per minute allowed"
                },
                headers={"Retry-After": "60"}
            )
        
        if len(hour_requests) >= self.requests_per_hour:
            logger.warning(f"Rate limit exceeded (per hour) for IP: {client_ip}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Maximum {self.requests_per_hour} requests per hour allowed"
                },
                headers={"Retry-After": "3600"}
            )
        
        # Add current request timestamp
        minute_requests.append(current_time)
        hour_requests.append(current_time)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit-Minute"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining-Minute"] = str(
            self.requests_per_minute - len(minute_requests)
        )
        response.headers["X-RateLimit-Limit-Hour"] = str(self.requests_per_hour)
        response.headers["X-RateLimit-Remaining-Hour"] = str(
            self.requests_per_hour - len(hour_requests)
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
