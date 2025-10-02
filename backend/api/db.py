import os
import json
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://rampart:rampart_dev_password@postgres:5432/rampart",
)

_engine: Optional[Engine] = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL, pool_pre_ping=True)
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


def get_default(key: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        res = conn.execute(
            text("SELECT value FROM policy_defaults WHERE key = :k"), {"k": key}
        ).fetchone()
        if not res:
            return None
        # SQLAlchemy returns a native dict for JSONB
        return res[0]


def set_default(key: str, value: Dict[str, Any]) -> None:
    with get_conn() as conn:
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
