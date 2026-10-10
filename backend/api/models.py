"""
SQLAlchemy ORM models.

These mirror the tables historically created by the hand-written DDL in
``api.db.init_*_table`` so that ORM code and legacy ``text()`` queries can run
side by side against the same database during the migration to the ORM.

Dialect notes
- ``GUID``: native UUID on PostgreSQL, dashed CHAR(36) on SQLite. Always a
  ``uuid.UUID`` in Python.
- ``JSONType``: JSONB on PostgreSQL, JSON on SQLite. Also used for string lists
  (``permissions``, ``tags``), which were TEXT[] on PostgreSQL before the
  ``text_arrays_to_jsonb`` Alembic revision.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    CHAR,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Dialect
from sqlalchemy.types import JSON, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class GUID(TypeDecorator[uuid.UUID]):
    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value: Any, dialect: Dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> Optional[uuid.UUID]:
        if value is None or isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


JSONType = JSON().with_variant(postgresql.JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class PolicyDefault(Base):
    __tablename__ = "policy_defaults"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("idx_users_email", "email"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))


class ProviderKey(Base):
    __tablename__ = "provider_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "provider"),
        Index("idx_provider_keys_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    last_4: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active", server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=func.now()
    )


DEFAULT_API_KEY_PERMISSIONS = ["security:analyze", "filter:pii", "llm:chat"]


class RampartApiKey(Base):
    __tablename__ = "rampart_api_keys"
    __table_args__ = (
        UniqueConstraint("key_prefix", "key_hash"),
        Index("idx_rampart_api_keys_user_id", "user_id"),
        Index("idx_rampart_api_keys_key_hash", "key_hash"),
        Index("idx_rampart_api_keys_active", "is_active"),
        Index("idx_rampart_api_keys_preview", "key_preview"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key_name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    key_preview: Mapped[str] = mapped_column(String(20), nullable=False)
    permissions: Mapped[Optional[list[str]]] = mapped_column(JSONType, default=lambda: list(DEFAULT_API_KEY_PERMISSIONS))
    rate_limit_per_minute: Mapped[Optional[int]] = mapped_column(Integer, default=60, server_default=text("60"))
    rate_limit_per_hour: Mapped[Optional[int]] = mapped_column(Integer, default=1000, server_default=text("1000"))
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, default=True, server_default=text("TRUE"))
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=func.now()
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    template_pack: Mapped[Optional[str]] = mapped_column(String(50))


class RampartApiKeyUsage(Base):
    __tablename__ = "rampart_api_key_usage"
    __table_args__ = (
        UniqueConstraint("api_key_id", "endpoint", "date", "hour"),
        Index("idx_api_key_usage_date", "date"),
        Index("idx_api_key_usage_key_id", "api_key_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    api_key_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("rampart_api_keys.id", ondelete="CASCADE"), nullable=False
    )
    endpoint: Mapped[str] = mapped_column(String(100), nullable=False)
    requests_count: Mapped[Optional[int]] = mapped_column(Integer, default=1, server_default=text("1"))
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, default=0, server_default=text("0"))
    cost_usd: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 6, asdecimal=False).with_variant(Float(), "sqlite"), default=0.0, server_default=text("0")
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, default=lambda: datetime.utcnow().date())
    hour: Mapped[int] = mapped_column(Integer, nullable=False, default=lambda: datetime.utcnow().hour)


class Policy(Base):
    __tablename__ = "policies"
    __table_args__ = (
        Index("idx_policies_user_id", "user_id"),
        Index("idx_policies_enabled", "enabled"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    policy_type: Mapped[str] = mapped_column(Text, nullable=False)
    rules: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    tags: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=func.now()
    )
    created_by: Mapped[Optional[str]] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_timestamp", "timestamp"),
        Index("idx_audit_logs_user_id", "user_id"),
        Index("idx_audit_logs_event_type", "event_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, server_default=func.now())
    user_id: Mapped[Optional[str]] = mapped_column(Text)
    api_key_preview: Mapped[Optional[str]] = mapped_column(Text)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    http_method: Mapped[str] = mapped_column(Text, nullable=False)
    ip_address: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[Optional[int]] = mapped_column(Integer)
    processing_time_ms: Mapped[Optional[float]] = mapped_column(Float)
    event_type: Mapped[str] = mapped_column(
        Text, nullable=False, default="api_request", server_default=text("'api_request'")
    )
    # "metadata" is reserved on declarative classes; the column keeps its DB name.
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONType, nullable=False, default=dict)


class InjectionFeedback(Base):
    __tablename__ = "injection_feedback"
    __table_args__ = (Index("idx_injection_feedback_sha", "content_sha256"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(32), nullable=False)
    verdict_seen: Mapped[Optional[str]] = mapped_column(String(16))
    profile: Mapped[Optional[str]] = mapped_column(String(32))
    category: Mapped[Optional[str]] = mapped_column(String(64))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    model_version: Mapped[Optional[str]] = mapped_column(String(200))
    policy_version: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, server_default=func.now())


__all__ = [
    "Base",
    "GUID",
    "JSONType",
    "DEFAULT_API_KEY_PERMISSIONS",
    "PolicyDefault",
    "User",
    "ProviderKey",
    "RampartApiKey",
    "RampartApiKeyUsage",
    "Policy",
    "AuditLog",
    "InjectionFeedback",
]
