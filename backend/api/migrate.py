"""
Bring the database schema to the current Alembic head.

Run at container start (see docker-entrypoint.sh) or manually:

    python -m api.migrate            # upgrade to head (idempotent)
    python -m api.migrate --check    # exit 1 if not at head, change nothing

Handles three states:
- fresh database        -> runs every migration
- legacy database       -> tables exist but no ``alembic_version`` (created by the
                           old ``api.db.init_*_table`` DDL); stamped at the baseline
                           revision, then upgraded
- already at head       -> no-op

On PostgreSQL a session-level advisory lock serialises concurrent starters so
only one process migrates at a time.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ADVISORY_LOCK_KEY = 0x52414D50  # "RAMP"
# Any of these existing without alembic_version means a pre-Alembic schema.
_LEGACY_MARKER_TABLES = ("users", "policy_defaults", "rampart_api_keys")


def alembic_config(connection: Connection | None = None) -> Config:
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    if connection is not None:
        cfg.attributes["connection"] = connection
    return cfg


def _head_revision(cfg: Config) -> str:
    heads = ScriptDirectory.from_config(cfg).get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"expected exactly one Alembic head, found {heads}")
    return heads[0]


def _base_revision(cfg: Config) -> str:
    bases = ScriptDirectory.from_config(cfg).get_bases()
    if len(bases) != 1:
        raise RuntimeError(f"expected exactly one Alembic base revision, found {bases}")
    return bases[0]


def _current_revision(connection: Connection) -> str | None:
    return MigrationContext.configure(connection).get_current_revision()


def _is_legacy_schema(connection: Connection) -> bool:
    tables = set(inspect(connection).get_table_names())
    return "alembic_version" not in tables and any(t in tables for t in _LEGACY_MARKER_TABLES)


def is_at_head(connection: Connection) -> bool:
    return _current_revision(connection) == _head_revision(alembic_config(connection))


def upgrade_database(connection: Connection) -> str:
    """Upgrade ``connection``'s database to head. Returns the resulting revision."""
    cfg = alembic_config(connection)
    head = _head_revision(cfg)
    pg = connection.dialect.name == "postgresql"

    if pg:
        connection.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _ADVISORY_LOCK_KEY})
    try:
        current = _current_revision(connection)
        if current == head:
            logger.info("Database schema already at head %s", head)
            return head

        if current is None and _is_legacy_schema(connection):
            base = _base_revision(cfg)
            logger.warning("Pre-Alembic schema detected; stamping baseline revision %s", base)
            command.stamp(cfg, base)
            current = base

        logger.info("Upgrading database schema %s -> %s", current or "<empty>", head)
        command.upgrade(cfg, "head")
        connection.commit()
        return head
    finally:
        if pg:
            connection.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _ADVISORY_LOCK_KEY})
            connection.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="report whether the schema is at head; change nothing")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    from api.db import DATABASE_URL, get_engine

    engine = get_engine()
    logger.info("Database: %s", engine.url.render_as_string(hide_password=True))
    with engine.connect() as conn:
        if args.check:
            current, head = _current_revision(conn), _head_revision(alembic_config(conn))
            if current == head:
                logger.info("Schema at head %s", head)
                return 0
            logger.error("Schema at %s, head is %s", current or "<none>", head)
            return 1
        try:
            upgrade_database(conn)
        except Exception:
            logger.exception("Database migration failed for %s", DATABASE_URL.split("@")[-1])
            return 1
    engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
