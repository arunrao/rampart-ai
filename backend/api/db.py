import os
import json
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Optional
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# Require DATABASE_URL to be set explicitly - no default credentials
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # For local development only, use SQLite
    DATABASE_URL = "sqlite:///./rampart_dev.db"
    import logging
    logging.warning("DATABASE_URL not set, using SQLite for development: %s", DATABASE_URL)

_engine: Optional[Engine] = None


def reset_engine() -> None:
    """Dispose and clear the global engine (used by tests to rebind DATABASE_URL)."""
    global _engine
    if _engine is not None:
        try:
            _engine.dispose()
        except Exception:
            pass
    _engine = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        # Optimize connection pooling for production
        # pool_size: Number of connections to keep open (default: 5)
        # max_overflow: Max connections beyond pool_size (default: 10)
        # pool_pre_ping: Test connections before using (prevents stale connections)
        # pool_recycle: Recycle connections after 1 hour (AWS RDS timeout is ~8h)
        _engine = create_engine(
            DATABASE_URL,
            pool_size=10,           # Keep 10 connections open
            max_overflow=20,        # Allow 20 additional connections during spikes
            pool_pre_ping=True,     # Test connection health before use
            pool_recycle=3600,      # Recycle connections every hour
            echo=False
        )
    return _engine


@contextmanager
def get_conn():
    engine = get_engine()
    conn = engine.connect()
    try:
        yield conn
    finally:
        conn.close()


def init_defaults_table() -> None:
    """Create a simple key->json defaults table if it doesn't exist."""
    with get_conn() as conn:
        # Check if we're using SQLite or PostgreSQL
        is_sqlite = "sqlite" in DATABASE_URL.lower()
        
        if is_sqlite:
            # SQLite version (uses TEXT instead of JSONB)
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS policy_defaults (
                      key TEXT PRIMARY KEY,
                      value TEXT NOT NULL,
                      updated_at TIMESTAMP NOT NULL
                    );
                    """
                )
            )
        else:
            # PostgreSQL version
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS policy_defaults (
                      key TEXT PRIMARY KEY,
                      value JSONB NOT NULL,
                      updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
                    );
                    """
                )
            )
        conn.commit()


@lru_cache(maxsize=32)  # Cache policy defaults (rarely change)
def get_default(key: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        res = conn.execute(
            text("SELECT value FROM policy_defaults WHERE key = :k"), {"k": key}
        ).fetchone()
        if not res:
            return None
        
        # Check if we're using SQLite or PostgreSQL
        is_sqlite = "sqlite" in DATABASE_URL.lower()
        
        if is_sqlite:
            # SQLite stores JSON as TEXT, need to parse it
            return json.loads(res[0])
        else:
            # SQLAlchemy returns a native dict for JSONB in PostgreSQL
            return res[0]


def set_default(key: str, value: Dict[str, Any]) -> None:
    with get_conn() as conn:
        # Check if we're using SQLite or PostgreSQL
        is_sqlite = "sqlite" in DATABASE_URL.lower()
        
        if is_sqlite:
            # SQLite version (uses REPLACE instead of ON CONFLICT)
            conn.execute(
                text(
                    """
                    INSERT OR REPLACE INTO policy_defaults (key, value, updated_at)
                    VALUES (:k, :v, :u)
                    """
                ),
                {"k": key, "v": json.dumps(value), "u": datetime.utcnow()},
            )
        else:
            # PostgreSQL version
            conn.execute(
                text(
                    """
                    INSERT INTO policy_defaults (key, value, updated_at)
                    VALUES (:k, :v::jsonb, :u)
                    ON CONFLICT (key)
                    DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at
                    """
                ),
                {"k": key, "v": json.dumps(value), "u": datetime.utcnow()},
            )
        conn.commit()


def init_users_table() -> None:
    """Create users table for authentication."""
    with get_conn() as conn:
        # Check if we're using SQLite or PostgreSQL
        is_sqlite = "sqlite" in DATABASE_URL.lower()
        
        if is_sqlite:
            # SQLite: one statement per execute (sqlite3 driver limitation)
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                      id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(lower(hex(randomblob(2))),2) || '-' || lower(hex(randomblob(6)))),
                      email TEXT UNIQUE NOT NULL,
                      password_hash TEXT NOT NULL,
                      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      is_active BOOLEAN NOT NULL DEFAULT 1
                    )
                    """
                )
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
            )
        else:
            # PostgreSQL version
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      email TEXT UNIQUE NOT NULL,
                      password_hash TEXT NOT NULL,
                      created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                      updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                      is_active BOOLEAN NOT NULL DEFAULT TRUE
                    )
                    """
                )
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
            )
        conn.commit()


def init_provider_keys_table() -> None:
    """Create provider_keys table for storing encrypted API keys."""
    with get_conn() as conn:
        # Check if we're using SQLite or PostgreSQL
        is_sqlite = "sqlite" in DATABASE_URL.lower()
        
        if is_sqlite:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS provider_keys (
                      id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(lower(hex(randomblob(2))),2) || '-' || lower(hex(randomblob(6)))),
                      user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                      provider TEXT NOT NULL,
                      key_encrypted TEXT NOT NULL,
                      last_4 TEXT NOT NULL,
                      status TEXT NOT NULL DEFAULT 'active',
                      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      UNIQUE(user_id, provider)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_provider_keys_user_id ON provider_keys(user_id)"
                )
            )
        else:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS provider_keys (
                      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                      provider TEXT NOT NULL,
                      key_encrypted TEXT NOT NULL,
                      last_4 TEXT NOT NULL,
                      status TEXT NOT NULL DEFAULT 'active',
                      created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                      updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                      UNIQUE(user_id, provider)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_provider_keys_user_id ON provider_keys(user_id)"
                )
            )
        conn.commit()


def init_rampart_api_keys_table() -> None:
    """Create rampart_api_keys table for application API keys."""
    with get_conn() as conn:
        # Check if we're using SQLite or PostgreSQL
        is_sqlite = "sqlite" in DATABASE_URL.lower()
        
        if is_sqlite:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS rampart_api_keys (
                      id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(lower(hex(randomblob(2))),2) || '-' || lower(hex(randomblob(6)))),
                      user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                      key_name TEXT NOT NULL,
                      key_prefix TEXT NOT NULL,
                      key_hash TEXT NOT NULL,
                      key_preview TEXT NOT NULL,
                      permissions TEXT DEFAULT '["security:analyze", "filter:pii", "llm:chat"]',
                      rate_limit_per_minute INTEGER DEFAULT 60,
                      rate_limit_per_hour INTEGER DEFAULT 1000,
                      is_active BOOLEAN DEFAULT 1,
                      last_used_at TIMESTAMP,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      expires_at TIMESTAMP,
                      UNIQUE(key_prefix, key_hash)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_rampart_api_keys_user_id ON rampart_api_keys(user_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_rampart_api_keys_key_hash ON rampart_api_keys(key_hash)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_rampart_api_keys_active ON rampart_api_keys(is_active)"
                )
            )
        else:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS rampart_api_keys (
                      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                      key_name VARCHAR(100) NOT NULL,
                      key_prefix VARCHAR(20) NOT NULL,
                      key_hash VARCHAR(255) NOT NULL,
                      key_preview VARCHAR(20) NOT NULL,
                      permissions TEXT[] DEFAULT ARRAY['security:analyze', 'filter:pii', 'llm:chat'],
                      rate_limit_per_minute INTEGER DEFAULT 60,
                      rate_limit_per_hour INTEGER DEFAULT 1000,
                      is_active BOOLEAN DEFAULT true,
                      last_used_at TIMESTAMP,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      expires_at TIMESTAMP,
                      UNIQUE(key_prefix, key_hash)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_rampart_api_keys_user_id ON rampart_api_keys(user_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_rampart_api_keys_key_hash ON rampart_api_keys(key_hash)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_rampart_api_keys_active ON rampart_api_keys(is_active)"
                )
            )
        conn.commit()


def init_rampart_api_key_usage_table() -> None:
    """Create rampart_api_key_usage table for tracking API key usage."""
    with get_conn() as conn:
        # Check if we're using SQLite or PostgreSQL
        is_sqlite = "sqlite" in DATABASE_URL.lower()
        
        if is_sqlite:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS rampart_api_key_usage (
                      id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(lower(hex(randomblob(2))),2) || '-' || lower(hex(randomblob(6)))),
                      api_key_id TEXT NOT NULL REFERENCES rampart_api_keys(id) ON DELETE CASCADE,
                      endpoint TEXT NOT NULL,
                      requests_count INTEGER DEFAULT 1,
                      tokens_used INTEGER DEFAULT 0,
                      cost_usd REAL DEFAULT 0,
                      date DATE NOT NULL DEFAULT (date('now')),
                      hour INTEGER NOT NULL DEFAULT (cast(strftime('%H', 'now') as integer)),
                      UNIQUE(api_key_id, endpoint, date, hour)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_api_key_usage_date ON rampart_api_key_usage(date)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_api_key_usage_key_id ON rampart_api_key_usage(api_key_id)"
                )
            )
        else:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS rampart_api_key_usage (
                      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      api_key_id UUID NOT NULL REFERENCES rampart_api_keys(id) ON DELETE CASCADE,
                      endpoint VARCHAR(100) NOT NULL,
                      requests_count INTEGER DEFAULT 1,
                      tokens_used INTEGER DEFAULT 0,
                      cost_usd DECIMAL(10,6) DEFAULT 0,
                      date DATE NOT NULL DEFAULT CURRENT_DATE,
                      hour INTEGER NOT NULL DEFAULT EXTRACT(HOUR FROM CURRENT_TIMESTAMP),
                      UNIQUE(api_key_id, endpoint, date, hour)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_api_key_usage_date ON rampart_api_key_usage(date)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_api_key_usage_key_id ON rampart_api_key_usage(api_key_id)"
                )
            )
        conn.commit()


def init_policies_table() -> None:
    """Create policies table for persistent policy storage."""
    with get_conn() as conn:
        is_sqlite = "sqlite" in DATABASE_URL.lower()

        if is_sqlite:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS policies (
                      id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(lower(hex(randomblob(2))),2) || '-' || lower(hex(randomblob(6)))),
                      user_id TEXT NOT NULL,
                      name TEXT NOT NULL,
                      description TEXT,
                      policy_type TEXT NOT NULL,
                      rules TEXT NOT NULL DEFAULT '[]',
                      enabled BOOLEAN NOT NULL DEFAULT 1,
                      tags TEXT NOT NULL DEFAULT '[]',
                      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      created_by TEXT,
                      version INTEGER NOT NULL DEFAULT 1
                    )
                    """
                )
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_policies_user_id ON policies(user_id)")
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_policies_enabled ON policies(enabled)")
            )
        else:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS policies (
                      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      user_id UUID NOT NULL,
                      name TEXT NOT NULL,
                      description TEXT,
                      policy_type TEXT NOT NULL,
                      rules JSONB NOT NULL DEFAULT '[]',
                      enabled BOOLEAN NOT NULL DEFAULT TRUE,
                      tags TEXT[] NOT NULL DEFAULT '{}',
                      created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                      updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                      created_by TEXT,
                      version INTEGER NOT NULL DEFAULT 1
                    )
                    """
                )
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_policies_user_id ON policies(user_id)")
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_policies_enabled ON policies(enabled)")
            )
        conn.commit()


def init_audit_logs_table() -> None:
    """Create audit_logs table for SOC2 Type II compliance."""
    with get_conn() as conn:
        is_sqlite = "sqlite" in DATABASE_URL.lower()

        if is_sqlite:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS audit_logs (
                      id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(lower(hex(randomblob(2))),2) || '-' || lower(hex(randomblob(6)))),
                      timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      user_id TEXT,
                      api_key_preview TEXT,
                      endpoint TEXT NOT NULL,
                      http_method TEXT NOT NULL,
                      ip_address TEXT NOT NULL,
                      status_code INTEGER,
                      processing_time_ms REAL,
                      event_type TEXT NOT NULL DEFAULT 'api_request',
                      metadata TEXT NOT NULL DEFAULT '{}'
                    )
                    """
                )
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp)")
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)")
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type)")
            )
        else:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS audit_logs (
                      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                      user_id TEXT,
                      api_key_preview TEXT,
                      endpoint TEXT NOT NULL,
                      http_method TEXT NOT NULL,
                      ip_address TEXT NOT NULL,
                      status_code INTEGER,
                      processing_time_ms REAL,
                      event_type TEXT NOT NULL DEFAULT 'api_request',
                      metadata JSONB NOT NULL DEFAULT '{}'
                    )
                    """
                )
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp)")
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)")
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type)")
            )
        conn.commit()


def migrate_add_template_pack_column() -> None:
    """Add template_pack column to rampart_api_keys if not already present."""
    with get_conn() as conn:
        is_sqlite = "sqlite" in DATABASE_URL.lower()
        try:
            if is_sqlite:
                # Check via PRAGMA whether column already exists
                cols = conn.execute(
                    text("PRAGMA table_info(rampart_api_keys)")
                ).fetchall()
                col_names = [row[1] for row in cols]
                if "template_pack" not in col_names:
                    conn.execute(
                        text("ALTER TABLE rampart_api_keys ADD COLUMN template_pack TEXT")
                    )
                    conn.commit()
            else:
                conn.execute(
                    text(
                        "ALTER TABLE rampart_api_keys ADD COLUMN IF NOT EXISTS template_pack VARCHAR(50)"
                    )
                )
                conn.commit()
        except Exception:
            pass


def insert_audit_log(
    endpoint: str,
    http_method: str,
    ip_address: str,
    event_type: str = "api_request",
    user_id: Optional[str] = None,
    api_key_preview: Optional[str] = None,
    status_code: Optional[int] = None,
    processing_time_ms: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Insert a single audit log entry. Silently ignores errors to never block requests."""
    try:
        with get_conn() as conn:
            is_sqlite = "sqlite" in DATABASE_URL.lower()
            meta_str = json.dumps(metadata or {})

            if is_sqlite:
                conn.execute(
                    text(
                        """
                        INSERT INTO audit_logs
                          (user_id, api_key_preview, endpoint, http_method, ip_address,
                           status_code, processing_time_ms, event_type, metadata, timestamp)
                        VALUES
                          (:user_id, :api_key_preview, :endpoint, :http_method, :ip_address,
                           :status_code, :processing_time_ms, :event_type, :metadata, :ts)
                        """
                    ),
                    {
                        "user_id": user_id,
                        "api_key_preview": api_key_preview,
                        "endpoint": endpoint,
                        "http_method": http_method,
                        "ip_address": ip_address,
                        "status_code": status_code,
                        "processing_time_ms": processing_time_ms,
                        "event_type": event_type,
                        "metadata": meta_str,
                        "ts": datetime.utcnow(),
                    },
                )
            else:
                conn.execute(
                    text(
                        """
                        INSERT INTO audit_logs
                          (user_id, api_key_preview, endpoint, http_method, ip_address,
                           status_code, processing_time_ms, event_type, metadata, timestamp)
                        VALUES
                          (:user_id, :api_key_preview, :endpoint, :http_method, :ip_address,
                           :status_code, :processing_time_ms, :event_type, :metadata::jsonb, :ts)
                        """
                    ),
                    {
                        "user_id": user_id,
                        "api_key_preview": api_key_preview,
                        "endpoint": endpoint,
                        "http_method": http_method,
                        "ip_address": ip_address,
                        "status_code": status_code,
                        "processing_time_ms": processing_time_ms,
                        "event_type": event_type,
                        "metadata": meta_str,
                        "ts": datetime.utcnow(),
                    },
                )
            conn.commit()
    except Exception:
        pass


def init_all_tables() -> None:
    """Initialize all database tables."""
    init_defaults_table()
    init_users_table()
    init_provider_keys_table()
    init_rampart_api_keys_table()
    init_rampart_api_key_usage_table()
    init_policies_table()
    init_audit_logs_table()
    migrate_add_template_pack_column()
