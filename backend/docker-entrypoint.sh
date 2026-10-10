#!/bin/sh
# Bring the database schema to the current Alembic head before starting the app.
# Idempotent: no-op when already at head; stamps pre-Alembic databases first.
# A failed migration aborts startup so we never serve against a mismatched schema.
# Set SKIP_DB_MIGRATE=1 to bypass (e.g. migrations run as a separate deploy step).
set -e

if [ "${SKIP_DB_MIGRATE:-0}" != "1" ]; then
    python -m api.migrate
fi

exec "$@"
