-- Bootstrap Rampart on an existing PostgreSQL server (not needed for docker-compose postgres:
-- that image creates user/db from POSTGRES_* env vars).
--
-- Run once as a superuser, e.g.:
--   psql -U postgres -h localhost -p 5432 -f backend/api/migrations/00_init_rampart_database.sql
--
-- Edit the password to match DATABASE_URL in your project .env (used by docker compose).

CREATE USER rampart WITH PASSWORD 'rampart_dev_password';

CREATE DATABASE rampart OWNER rampart;

GRANT ALL PRIVILEGES ON DATABASE rampart TO rampart;

\c rampart

GRANT ALL ON SCHEMA public TO rampart;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO rampart;
