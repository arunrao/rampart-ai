"""text arrays to jsonb

rampart_api_keys.permissions and policies.tags were TEXT[] on PostgreSQL but
JSON text on SQLite, which forced dialect branches in every reader/writer.
Both become JSONB so one representation (a JSON array of strings) works
everywhere. SQLite already stores JSON text, so this is PostgreSQL-only.

Revision ID: 436a1817ee70
Revises: af6af926a5a0
Create Date: 2026-10-09 10:19:48.127000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '436a1817ee70'
down_revision: Union[str, None] = 'af6af926a5a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COLUMNS = (
    # (table, column, jsonb default)
    ("rampart_api_keys", "permissions", '\'["security:analyze", "filter:pii", "llm:chat"]\'::jsonb'),
    ("policies", "tags", "'[]'::jsonb"),
)


def _udt(table: str, column: str) -> str:
    return op.get_bind().execute(
        sa.text(
            "SELECT udt_name FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).scalar_one()


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table, column, default in _COLUMNS:
        if _udt(table, column) == "jsonb":
            continue  # already converted (e.g. created by the current legacy DDL)
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE jsonb USING to_jsonb({column})")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT {default}")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    defaults = {
        "permissions": "ARRAY['security:analyze', 'filter:pii', 'llm:chat']",
        "tags": "'{}'::text[]",
    }
    for table, column, _ in _COLUMNS:
        if _udt(table, column) != "jsonb":
            continue
        # ALTER ... USING cannot contain a subquery, so convert via a temporary column.
        tmp = f"{column}__arr"
        op.execute(f"ALTER TABLE {table} ADD COLUMN {tmp} text[]")
        op.execute(
            f"UPDATE {table} SET {tmp} = ARRAY(SELECT jsonb_array_elements_text({column})) "
            f"WHERE {column} IS NOT NULL"
        )
        op.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
        op.execute(f"ALTER TABLE {table} RENAME COLUMN {tmp} TO {column}")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT {defaults[column]}")
        if column == "tags":
            op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET NOT NULL")
