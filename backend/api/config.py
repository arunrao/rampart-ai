"""
Configuration management for Project Rampart
"""
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, model_validator
from functools import lru_cache
from typing import Literal, Optional


MIN_JWT_SECRET_LENGTH = 32
MIN_KEY_ENCRYPTION_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    app_name: str = "Project Rampart"
    app_version: str = "0.2.6"
    environment: str = "development"
    debug: bool = False
    secret_key: str = Field(default="")
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    
    # Database
    database_url: str = Field(default="sqlite:///./rampart.db")
    redis_url: str = "redis://localhost:6379/0"
    
    # LLM Providers
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    
    # Google OAuth
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: str = Field(default="http://localhost:8000/api/v1/auth/callback/google")
    frontend_url: str = Field(default="http://localhost:3000")
    
    # Security
    jwt_secret_key: str = Field(default="")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    key_encryption_secret: str = Field(default="")  # For encrypting user API keys
    # Optional per-deployment PBKDF2 salt for key_encryption_secret (see api/security/crypto.py).
    # Changing it on an existing deployment invalidates all stored provider keys.
    key_encryption_salt: str = Field(default="")

    # Dashboard session cookie (HttpOnly; set by the OAuth callback, cleared by /auth/logout).
    # Set session_cookie_domain when the API and dashboard live on different subdomains
    # (e.g. ".example.com"); leave empty when they share a host or for localhost.
    session_cookie_name: str = "rampart_session"
    session_cookie_domain: str = ""
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"  # "none" requires HTTPS
    
    # Content Filtering
    max_token_limit: int = 4096
    max_filter_content_chars: int = 100_000  # Upper bound for authenticated /filter content
    enable_pii_detection: bool = True
    enable_toxicity_detection: bool = True
    toxicity_threshold: float = 0.7
    
    # Prompt Injection Detection
    prompt_injection_detector: str = "hybrid"  # hybrid, deberta, regex
    prompt_injection_use_onnx: bool = True  # Use ONNX optimization for 3x faster inference
    prompt_injection_fast_mode: bool = False  # Skip DeBERTa for low-latency
    prompt_injection_threshold: float = 0.75  # Confidence threshold for blocking
    # When True (default), PII / toxicity / prompt-injection work runs concurrently (lower wall time).
    content_filter_parallel_ml: bool = True
    # Unauthenticated playground for marketing demos. Off by default: it exposes ML
    # inference to anonymous callers and is only protected by the per-IP rate limiter.
    enable_public_filter_demo: bool = False
    public_filter_demo_max_chars: int = 8000
    
    # Observability
    enable_tracing: bool = True
    enable_metrics: bool = True
    trace_sample_rate: float = 1.0
    
    # Policy Engine
    default_policy_mode: str = "monitor"  # monitor, block, redact
    enable_auto_remediation: bool = False
    
    # Number of reverse proxies in front of the API that append to X-Forwarded-For
    # (e.g. 1 for an AWS ALB). 0 = ignore forwarding headers and use the socket peer,
    # since clients can set X-Forwarded-For to anything.
    trusted_proxy_count: int = 0

    # Rate Limiting
    rate_limit_per_minute: int = 1000
    rate_limit_per_hour: int = 10000

    # Super-admin access (comma-separated list of email addresses)
    # e.g. SUPER_ADMIN_EMAILS=you@example.com,colleague@example.com
    super_admin_emails: str = ""

    # Audit logging — set to false if you handle access logs externally
    # (your own SIEM, Datadog, CloudWatch, etc.). The admin /stats endpoint
    # degrades gracefully when this is off; only the request-volume metrics
    # are unavailable. Policy config-change events are also suppressed.
    audit_log_enabled: bool = True

    # CORS Configuration
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:8080,http://localhost:8081"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

    @model_validator(mode="after")
    def _require_strong_jwt_secret(self) -> "Settings":
        # An empty/short HS256 key lets anyone forge tokens for any user (incl. super-admins).
        if len(self.jwt_secret_key or "") < MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                f"JWT_SECRET_KEY must be set to at least {MIN_JWT_SECRET_LENGTH} characters "
                "(generate one with: python generate_secrets.py)"
            )
        # Same bar for the key that protects stored provider API keys: the PBKDF2 salt is
        # fixed per deployment, so a short secret is directly brute-forceable from a DB dump.
        if len(self.key_encryption_secret or "") < MIN_KEY_ENCRYPTION_SECRET_LENGTH:
            raise ValueError(
                f"KEY_ENCRYPTION_SECRET must be set to at least {MIN_KEY_ENCRYPTION_SECRET_LENGTH} characters "
                "(generate one with: python generate_secrets.py)"
            )
        if self.environment.lower() == "production":
            for name, value in (("JWT_SECRET_KEY", self.jwt_secret_key),
                                ("KEY_ENCRYPTION_SECRET", self.key_encryption_secret)):
                if "change-in-production" in value:
                    raise ValueError(f"{name} is still a placeholder value; set a real secret in production")
            if self.debug:
                raise ValueError("DEBUG must be false in production (it echoes exception text to clients)")
        return self

    @field_validator("session_cookie_samesite", mode="before")
    @classmethod
    def _normalize_samesite(cls, v):
        # Accept "Lax" / "NONE" etc. from env vars; the Literal type then enforces the allowed set
        return v.strip().lower() if isinstance(v, str) else v


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
