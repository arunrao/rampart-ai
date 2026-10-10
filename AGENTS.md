# Project notes

## Backend (FastAPI, `backend/`)

- Python env: `backend/venv` (`./venv/bin/python`).
- Tests: `cd backend && ./venv/bin/python -m pytest -q` (uses an isolated SQLite DB; secrets are set in `tests/conftest.py`).
- Database access is SQLAlchemy 2.0. ORM models live in `api/models.py`; `api/db.py` exposes
  `get_session()` / `get_db()` (ORM) alongside the legacy `get_conn()` + `text()` path that most routes still use.
  New DB code should use the ORM/Core expressions, not raw SQL strings.
- Schema: SQLite (dev/tests) is created by `api.db.init_all_tables()` / `create_all_tables()`.
  PostgreSQL is managed by Alembic (`backend/alembic/`). The container entrypoint runs
  `python -m api.migrate` (idempotent, auto-stamps pre-Alembic DBs) before uvicorn; see `backend/alembic/README`.
  Schema changes = edit `api/models.py` + `alembic revision --autogenerate`; never hand-edit tables.
- Raw `text()` SQL on PostgreSQL: write casts as `CAST(:param AS JSONB)`, never `:param::jsonb`
  (SQLAlchemy does not recognise a bind param followed by `::`). JSON-array columns
  (`rampart_api_keys.permissions`, `policies.tags`, `rules`, `metadata`, `value`) are JSONB on PG /
  JSON text on SQLite: bind `json.dumps(...)`, never a Python list.
- Route conversion pattern (see `api/routes/providers.py`): `db: Session = Depends(get_db)`,
  `select(Model).where(...)`, `db.add()/db.delete()`, explicit `db.commit()` after writes; a small
  `_to_response(model)` replaces positional `row[n]` unpacking. Non-request helpers use
  `with get_session() as db:`. Keep aggregates (admin stats) as Core `select()`/`func`, not ORM objects.
- Tests seed data with ORM objects (`tests/helpers.py`, fixtures) rather than `text()` inserts, so the
  suite runs on both SQLite and Postgres. CI (`.github/workflows/backend-tests.yml`) runs both.
  Locally: `DATABASE_URL=postgresql://... ./venv/bin/python -m pytest -q` against any scratch Postgres.
- `tests/test_orm_models.py` fails if the ORM models, the legacy DDL, and the Alembic head drift apart.

## Prompt-injection detector (`backend/models/`)

- Pipeline: `injection_normalize.py` (NFKC, zero-width/tag chars, hidden channels, decode) →
  regex rules in `prompt_injection_detector.py` → token-chunked DeBERTa → `injection_policy.py`
  (profiles, strong/weak/supply-chain tiers, rule-based verdict) → optional `injection_arbiter.py`.
- Verdicts are `allow | monitor | flag | block | unavailable`. `unavailable` (HTTP 503 on
  `/scan/injection`) is the fail-closed replacement for ALLOW whenever the classifier did not fully run.
  Never add a code path that turns a model error into `allow`.
- Adding a rule: add the `InjectionPattern`, put its name in exactly one tier set in
  `injection_policy.py` (`test_all_pattern_names_are_tiered` enforces this), and add ≥5 positives and
  ≥5 near-miss negatives to `PATTERN_CASES` in `tests/test_prompt_injection.py`.
- Tests: unit/API tests run without the model (`tests/test_prompt_injection.py`,
  `tests/test_injection_fail_closed.py`, `tests/test_scan_injection_api.py`). Model-backed regression
  pins: `RAMPART_MODEL_TESTS=1 ./venv/bin/python -m pytest tests/test_injection_regression.py`.
- Eval: `make eval-corpus` (fetches ~1,350 public docs into `backend/eval/corpus/`, gitignored),
  `make eval-smoke` (regex only), `make eval-gates` (full model run, gates in `backend/eval/gates.json`).
  Known gaps that must not gate live in `backend/eval/known_gaps.json`.
## Policies (`backend/api/routes/policies.py`)

- `_evaluate_condition` uses GLiNER for `contains_pii` / `contains_phi` when importable; an empty GLiNER
  result is final (no regex fallthrough), the regex/keyword path only runs if GLiNER is absent or raises.
  `contains_phi` matches `PIIEntity.type` values from `GLiNERPIIDetector._map_label_to_type`
  (`date_of_birth`, `medical_record`) — keep the two in sync.
- Tests: `tests/test_policies_user_defined.py` (fast; regex path + stubbed-GLiNER integration branches),
  `tests/test_policy_security.py`. Real-model pins (gliner-pii-small, ~2s load from HF cache):
  `RAMPART_MODEL_TESTS=1 ./venv/bin/python -m pytest tests/test_policies_gliner.py`.

- `tests/test_data_exfiltration.py::test_granular_severity_bulk_vs_targeted` is order-dependent and
  fails in the full suite on `main` as well (pre-existing); it passes in isolation.

## Deploying (AWS, `aws/`)

- Production does **not** deploy from git automatically. `make deploy` (= `aws/update.sh`) builds both
  images locally for linux/amd64, tags `:<short-sha>` + `:latest`, pushes to ECR and starts an ASG
  instance refresh. It refuses a dirty tree or a branch other than `main`; the SHA must exist on
  `origin/main`. Use `--backend-only` / `--frontend-only` / `--no-refresh` / `--allow-dirty` as needed.
- Container env vars (incl. `SUPER_ADMIN_EMAILS`, `ENABLE_PUBLIC_FILTER_DEMO`, `ACCESS_TOKEN_EXPIRE_MINUTES`)
  live in the compose block of `aws/cloudformation/infrastructure.yaml`. Changing them = `make deploy-infra`
  (`aws/deploy.sh`, needs `aws/.env`) *then* a refresh so instances pick up the new launch template.
- `make smoke` is the post-deploy check; it also prints which SHA tag `:latest` points at in ECR.
- Secrets: `JWT_SECRET_KEY` and `KEY_ENCRYPTION_SECRET` are currently the *same* Secrets Manager value
  in production (`JWT_KEY`); rotating the encryption secret invalidates stored provider keys.
- Operator scripts (`backend/scripts/`: token minting, demo seeding, model smoke tests) are excluded
  from the image via `backend/.dockerignore`; run them from `backend/` with `./venv/bin/python scripts/<name>.py`.

## Dependencies / CI

- `make typecheck` (pyright over `backend/`, tsc over `frontend/`) must be clean; CI runs pyright on the
  sqlite leg of `backend-tests.yml`. New `str = None` defaults etc. will fail the build.
- `make audit` runs pip-audit + `npm audit --audit-level=high`. Remaining npm findings are build-time
  glob/PostCSS DoS rooted in `tailwindcss@3`; fixing them means Tailwind 4.
- `optimum[onnxruntime]` is intentionally absent (`optimum-onnx` pins `transformers<4.58`); DeBERTa and
  toxic-bert run on PyTorch, GLiNER uses onnxruntime directly. Re-add when optimum-onnx supports transformers 5.
- `openai` / `anthropic` SDKs are required (LLM proxy, injection arbiter). The arbiter is validated at
  startup in `api/main.py` lifespan: enabled without SDK or API key is a hard error, not a warning.
- Workflows run with `permissions: contents: read` and SHA-pinned actions; Dependabot (`.github/dependabot.yml`)
  bumps actions/pip/npm weekly, excluding major bumps of transformers/torch/next/react.
