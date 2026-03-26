"""
Configuration management for Project Rampart
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import Optional


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
    
    # Content Filtering
    max_token_limit: int = 4096
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
    # Unauthenticated playground for marketing / self-host (disable in strict production)
    enable_public_filter_demo: bool = True
    public_filter_demo_max_chars: int = 8000
    
    # Observability
    enable_tracing: bool = True
    enable_metrics: bool = True
    trace_sample_rate: float = 1.0
    
    # Policy Engine
    default_policy_mode: str = "monitor"  # monitor, block, redact
    enable_auto_remediation: bool = False
    
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


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
