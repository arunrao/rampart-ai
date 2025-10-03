"""
Configuration management for Project Rampart
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    app_name: str = "Project Rampart"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True
    secret_key: str
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    
    # Database
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    
    # LLM Providers
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    
    # Google OAuth
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/callback/google"
    
    # Security
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    key_encryption_secret: str  # For encrypting user API keys
    
    # Content Filtering
    max_token_limit: int = 4096
    enable_pii_detection: bool = True
    enable_toxicity_detection: bool = True
    toxicity_threshold: float = 0.7
    
    # Observability
    enable_tracing: bool = True
    enable_metrics: bool = True
    trace_sample_rate: float = 1.0
    
    # Policy Engine
    default_policy_mode: str = "monitor"  # monitor, block, redact
    enable_auto_remediation: bool = False
    
    # Rate Limiting
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
