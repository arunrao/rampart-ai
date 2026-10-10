"""baseline existing schema

Captures the schema previously created by api.db.init_*_table() (and the former
runtime DDL for injection_feedback, now an ORM model). Databases that already have
these tables should be marked with ``alembic stamp af6af926a5a0`` rather than
upgraded.

Revision ID: af6af926a5a0
Revises: 
Create Date: 2026-10-09 09:36:28.108995

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from sqlalchemy.dialects import postgresql

from api.models import GUID, JSONType

# TEXT[] on PostgreSQL / JSON on SQLite, as the legacy DDL created it. Converted to
# JSONB by the following revision; kept here so this baseline stays historically exact.
StringArray = postgresql.ARRAY(sa.Text()).with_variant(sa.JSON(), "sqlite")


# revision identifiers, used by Alembic.
revision: str = 'af6af926a5a0'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


# Dashed UUID v4 in SQLite, as the legacy DDL generated it.
_SQLITE_UUID = (
    "(lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || "
    "substr(lower(hex(randomblob(2))),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || "
    "substr(lower(hex(randomblob(2))),2) || '-' || lower(hex(randomblob(6))))"
)


def _id() -> sa.Column:
    default = sa.text("gen_random_uuid()") if _pg() else sa.text(_SQLITE_UUID)
    return sa.Column("id", GUID(), primary_key=True, server_default=default)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(), nullable=nullable, server_default=sa.func.now())


def upgrade() -> None:
    pg = _pg()
    true = sa.text("TRUE") if pg else sa.text("1")

    op.create_table(
        "policy_defaults",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", JSONType, nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "users",
        _id(),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=true),
    )
    op.create_index("idx_users_email", "users", ["email"])

    op.create_table(
        "provider_keys",
        _id(),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("key_encrypted", sa.Text(), nullable=False),
        sa.Column("last_4", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        _ts("created_at"),
        _ts("updated_at"),
        sa.UniqueConstraint("user_id", "provider"),
    )
    op.create_index("idx_provider_keys_user_id", "provider_keys", ["user_id"])

    permissions_default = (
        sa.text("ARRAY['security:analyze', 'filter:pii', 'llm:chat']")
        if pg
        else sa.text("'[\"security:analyze\", \"filter:pii\", \"llm:chat\"]'")
    )
    op.create_table(
        "rampart_api_keys",
        _id(),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key_name", sa.String(100), nullable=False),
        sa.Column("key_prefix", sa.String(20), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False),
        sa.Column("key_preview", sa.String(20), nullable=False),
        sa.Column("permissions", StringArray, server_default=permissions_default),
        sa.Column("rate_limit_per_minute", sa.Integer(), server_default=sa.text("60")),
        sa.Column("rate_limit_per_hour", sa.Integer(), server_default=sa.text("1000")),
        sa.Column("is_active", sa.Boolean(), server_default=true),
        sa.Column("last_used_at", sa.DateTime()),
        _ts("created_at", nullable=True),
        _ts("updated_at", nullable=True),
        sa.Column("expires_at", sa.DateTime()),
        sa.Column("template_pack", sa.String(50)),
        sa.UniqueConstraint("key_prefix", "key_hash"),
    )
    op.create_index("idx_rampart_api_keys_user_id", "rampart_api_keys", ["user_id"])
    op.create_index("idx_rampart_api_keys_key_hash", "rampart_api_keys", ["key_hash"])
    op.create_index("idx_rampart_api_keys_active", "rampart_api_keys", ["is_active"])
    op.create_index("idx_rampart_api_keys_preview", "rampart_api_keys", ["key_preview"])

    op.create_table(
        "rampart_api_key_usage",
        _id(),
        sa.Column("api_key_id", GUID(), sa.ForeignKey("rampart_api_keys.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint", sa.String(100), nullable=False),
        sa.Column("requests_count", sa.Integer(), server_default=sa.text("1")),
        sa.Column("tokens_used", sa.Integer(), server_default=sa.text("0")),
        sa.Column(
            "cost_usd",
            sa.Numeric(10, 6).with_variant(sa.Float(), "sqlite"),
            server_default=sa.text("0"),
        ),
        sa.Column(
            "date", sa.Date(), nullable=False,
            server_default=sa.text("CURRENT_DATE") if pg else sa.text("(date('now'))"),
        ),
        sa.Column(
            "hour", sa.Integer(), nullable=False,
            server_default=sa.text("EXTRACT(HOUR FROM CURRENT_TIMESTAMP)") if pg
            else sa.text("(cast(strftime('%H', 'now') as integer))"),
        ),
        sa.UniqueConstraint("api_key_id", "endpoint", "date", "hour"),
    )
    op.create_index("idx_api_key_usage_date", "rampart_api_key_usage", ["date"])
    op.create_index("idx_api_key_usage_key_id", "rampart_api_key_usage", ["api_key_id"])

    op.create_table(
        "policies",
        _id(),
        sa.Column("user_id", GUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("policy_type", sa.Text(), nullable=False),
        sa.Column("rules", JSONType, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=true),
        sa.Column("tags", StringArray, nullable=False, server_default=sa.text("'{}'") if pg else sa.text("'[]'")),
        _ts("created_at"),
        _ts("updated_at"),
        sa.Column("created_by", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.create_index("idx_policies_user_id", "policies", ["user_id"])
    op.create_index("idx_policies_enabled", "policies", ["enabled"])

    op.create_table(
        "audit_logs",
        _id(),
        _ts("timestamp"),
        sa.Column("user_id", sa.Text()),
        sa.Column("api_key_preview", sa.Text()),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("http_method", sa.Text(), nullable=False),
        sa.Column("ip_address", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer()),
        sa.Column("processing_time_ms", sa.Float()),
        sa.Column("event_type", sa.Text(), nullable=False, server_default=sa.text("'api_request'")),
        sa.Column("metadata", JSONType, nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index("idx_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("idx_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("idx_audit_logs_event_type", "audit_logs", ["event_type"])

    op.create_table(
        "injection_feedback",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("label", sa.String(32), nullable=False),
        sa.Column("verdict_seen", sa.String(16)),
        sa.Column("profile", sa.String(32)),
        sa.Column("category", sa.String(64)),
        sa.Column("notes", sa.Text()),
        sa.Column("model_version", sa.String(200)),
        sa.Column("policy_version", sa.String(64)),
        _ts("created_at"),
    )
    op.create_index("idx_injection_feedback_sha", "injection_feedback", ["content_sha256"])


def downgrade() -> None:
    for table in (
        "injection_feedback",
        "audit_logs",
        "policies",
        "rampart_api_key_usage",
        "rampart_api_keys",
        "provider_keys",
        "users",
        "policy_defaults",
    ):
        op.drop_table(table)
