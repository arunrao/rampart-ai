"""ORM foundation: models match the legacy DDL, Alembic baseline matches the models,
and ORM-written rows are readable by legacy text() queries (and vice versa)."""
from __future__ import annotations

import json
import pathlib
import uuid
from datetime import datetime

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from api.models import (
    AuditLog,
    Base,
    Policy,
    RampartApiKey,
    RampartApiKeyUsage,
    User,
)
from tests.helpers import create_user_and_jwt

_BACKEND = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def legacy_engine(tmp_path_factory):
    """A SQLite DB built by the legacy api.db.init_*_table() DDL (not Alembic)."""
    import api.db as db

    url = f"sqlite:///{tmp_path_factory.mktemp('legacy') / 'legacy.sqlite'}"
    saved = db.DATABASE_URL
    db.DATABASE_URL = url
    db.reset_engine()
    try:
        db.init_all_tables()
    finally:
        db.DATABASE_URL = saved
        db.reset_engine()
    engine = create_engine(url)
    yield engine
    engine.dispose()


def test_models_match_legacy_ddl_tables(legacy_engine):
    insp = inspect(legacy_engine)
    live = set(insp.get_table_names())
    declared = set(Base.metadata.tables)
    assert declared <= live, f"models declare tables the legacy DDL does not create: {declared - live}"


@pytest.mark.parametrize("table_name", sorted(Base.metadata.tables))
def test_model_columns_match_legacy_ddl(legacy_engine, table_name: str):
    insp = inspect(legacy_engine)
    live = {c["name"]: c for c in insp.get_columns(table_name)}
    model = Base.metadata.tables[table_name]

    assert set(live) == set(model.columns.keys()), (
        f"{table_name}: column mismatch; only in DB={set(live) - set(model.columns.keys())}, "
        f"only in model={set(model.columns.keys()) - set(live)}"
    )
    for col in model.columns:
        if col.primary_key:
            continue  # SQLite reports non-INTEGER PRIMARY KEY columns as nullable
        assert live[col.name]["nullable"] == col.nullable, f"{table_name}.{col.name}: nullable differs"

    live_pk = set(insp.get_pk_constraint(table_name)["constrained_columns"])
    assert live_pk == {c.name for c in model.primary_key.columns}, f"{table_name}: primary key differs"

    live_idx = {i["name"] for i in insp.get_indexes(table_name) if i["name"] and not i["name"].startswith("sqlite_")}
    assert {i.name for i in model.indexes} <= live_idx, f"{table_name}: model declares indexes missing from DB"


def test_alembic_baseline_matches_models(tmp_path, monkeypatch):
    db_path = tmp_path / "alembic.sqlite"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.chdir(_BACKEND)

    cfg = Config(str(_BACKEND / "alembic.ini"))
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    with engine.connect() as conn:
        diffs = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diffs == [], f"models and Alembic head disagree: {diffs}"

    # Legacy DDL on top of the Alembic schema must be a no-op (prod `alembic stamp` path).
    import api.db as db

    monkeypatch.setattr(db, "DATABASE_URL", url)
    db.reset_engine()
    try:
        db.init_all_tables()
    finally:
        db.reset_engine()
        monkeypatch.delenv("DATABASE_URL")
    with engine.connect() as conn:
        diffs = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diffs == []
    engine.dispose()


def test_orm_and_legacy_sql_interoperate():
    from api.db import get_conn, get_session

    _, uid, _ = create_user_and_jwt()
    with get_session() as s:
        key = RampartApiKey(user_id=uid, key_name="orm", key_prefix="rmp_", key_hash=uuid.uuid4().hex, key_preview="rmp_orm")
        s.add(key)
        s.flush()
        s.add(RampartApiKeyUsage(api_key_id=key.id, endpoint="/filter", requests_count=3))
        s.add(Policy(user_id=uid, name="p", policy_type="content_filter", rules=[{"id": "r1"}], tags=["a"]))
        s.add(AuditLog(endpoint="/x", http_method="GET", ip_address="127.0.0.1", metadata_={"k": 1}))
        key_id = key.id

    # Legacy text() reads: dashed-UUID string + JSON text on SQLite, UUID + list on PostgreSQL.
    with get_conn() as conn:
        row = conn.execute(text("SELECT id, permissions FROM rampart_api_keys WHERE id = :id"), {"id": str(key_id)}).fetchone()
        assert row is not None and str(row[0]) == str(key_id)
        perms = row[1] if isinstance(row[1], list) else json.loads(row[1])
        assert "security:analyze" in perms
        assert conn.execute(text("SELECT requests_count FROM rampart_api_key_usage WHERE api_key_id = :k"), {"k": str(key_id)}).scalar() == 3

    # Legacy write (as the routes do today) is readable through the ORM.
    other = uuid.uuid4()
    with get_conn() as conn:
        conn.execute(
            text("INSERT INTO users (id, email, password_hash, created_at, updated_at, is_active) VALUES (:id, :e, 'x', :n, :n, :a)"),
            {"id": str(other), "e": f"legacy_{other.hex[:8]}@example.com", "n": datetime.utcnow(), "a": True},
        )
        conn.commit()
    with get_session() as s:
        user = s.get(User, other)
        assert user is not None and user.is_active is True and isinstance(user.id, uuid.UUID)
        policy = s.query(Policy).filter_by(user_id=uid).one()
        assert policy.rules == [{"id": "r1"}] and policy.tags == ["a"]
        assert s.query(AuditLog).filter_by(endpoint="/x").one().metadata_ == {"k": 1}


def _diffs(engine):
    with engine.connect() as conn:
        return compare_metadata(MigrationContext.configure(conn), Base.metadata)


def test_upgrade_database_fresh_then_idempotent(tmp_path):
    from api import migrate

    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.sqlite'}")
    with engine.connect() as conn:
        assert migrate.upgrade_database(conn) == migrate._head_revision(migrate.alembic_config())
        assert migrate.is_at_head(conn)
    assert _diffs(engine) == []
    with engine.connect() as conn:  # second run is a no-op
        migrate.upgrade_database(conn)
        assert migrate.is_at_head(conn)
    engine.dispose()


def test_upgrade_database_stamps_legacy_schema(tmp_path, monkeypatch):
    """A DB created by the old init_*_table() DDL has no alembic_version: it must be
    stamped at the baseline (not re-created) and end up at head with its data intact."""
    import api.db as db
    from api import migrate

    url = f"sqlite:///{tmp_path / 'legacy.sqlite'}"
    monkeypatch.setattr(db, "DATABASE_URL", url)
    db.reset_engine()
    try:
        db.init_all_tables()
        db.set_default("k", {"v": 1})
    finally:
        db.reset_engine()
        db.get_default.cache_clear()

    engine = create_engine(url)
    with engine.connect() as conn:
        assert "alembic_version" not in inspect(conn).get_table_names()
        assert migrate._is_legacy_schema(conn)
        migrate.upgrade_database(conn)
        assert migrate.is_at_head(conn)
        assert conn.execute(text("SELECT value FROM policy_defaults WHERE key = 'k'")).scalar() is not None
        # Stamped, not re-created: the legacy SQLite column types (TEXT ids, TIMESTAMP) remain.
        assert inspect(conn).get_columns("users")[0]["type"].__class__.__name__ == "TEXT"
    engine.dispose()


def test_migrate_cli_check(tmp_path, monkeypatch):
    import api.db as db
    from api import migrate

    url = f"sqlite:///{tmp_path / 'cli.sqlite'}"
    monkeypatch.setattr(db, "DATABASE_URL", url)
    db.reset_engine()
    try:
        assert migrate.main(["--check"]) == 1  # empty DB is not at head
        assert migrate.main([]) == 0
        assert migrate.main(["--check"]) == 0
    finally:
        db.reset_engine()


def test_get_session_rolls_back_on_error():
    from api.db import get_session

    email = f"rollback_{uuid.uuid4().hex[:8]}@example.com"
    with pytest.raises(RuntimeError):
        with get_session() as s:
            s.add(User(email=email, password_hash="x"))
            s.flush()
            raise RuntimeError("boom")
    with get_session() as s:
        assert s.query(User).filter_by(email=email).first() is None
