.PHONY: help setup install start start-backend start-frontend stop \
        test test-backend test-backend-pg test-frontend test-models \
        lint typecheck audit migrate migrate-check migrate-new \
        eval-corpus eval-gates eval-smoke \
        docker-up docker-down docker-logs docker-rebuild \
        deploy deploy-backend deploy-frontend deploy-infra smoke \
        clean health-check examples dev prod-build

PY      := backend/venv/bin/python
PIP     := $(PY) -m pip
ALEMBIC := backend/venv/bin/alembic
PROD_URL ?= https://rampart.arunrao.com

help:
	@echo "Project Rampart"
	@echo ""
	@echo "Local dev"
	@echo "  setup / install        bootstrap venv + node_modules"
	@echo "  start | stop           run (or kill) backend + frontend dev servers"
	@echo "  docker-up/down/logs    docker compose stack (postgres, redis, api, web, jaeger)"
	@echo "  migrate | migrate-check   apply Alembic migrations / verify schema is at head"
	@echo "  migrate-new m=\"msg\"    autogenerate a migration from api/models.py"
	@echo ""
	@echo "Quality"
	@echo "  test                   backend (sqlite) + frontend unit tests"
	@echo "  test-backend-pg        backend tests against DATABASE_URL (a scratch Postgres)"
	@echo "  test-models            model-backed regression pins (needs HF cache)"
	@echo "  lint | typecheck       eslint + pyright"
	@echo "  audit                  pip-audit + npm audit"
	@echo "  eval-smoke/eval-gates  prompt-injection eval (see backend/eval)"
	@echo ""
	@echo "Production (AWS)"
	@echo "  deploy                 build :SHA + :latest, push to ECR, roll instances"
	@echo "  deploy-backend / deploy-frontend   one image only"
	@echo "  deploy-infra           CloudFormation stack update (env vars, instance type, ...)"
	@echo "  smoke                  curl checks against \$$PROD_URL ($(PROD_URL))"

# ---------------------------------------------------------------------------
# Local dev
# ---------------------------------------------------------------------------
setup:
	@./setup.sh

install:
	@echo "Installing backend dependencies..."
	@cd backend && python3 -m venv venv && ./venv/bin/pip install --upgrade pip && ./venv/bin/pip install -r requirements.txt
	@echo "Installing frontend dependencies..."
	@cd frontend && npm ci

start:
	@echo "Backend  -> http://localhost:8000/api/v1/docs"
	@echo "Frontend -> http://localhost:3000"
	@$(MAKE) -j2 start-backend start-frontend

start-backend:
	@cd backend && ./venv/bin/uvicorn api.main:app --reload

start-frontend:
	@cd frontend && npm run dev

stop:
	@pkill -f "uvicorn api.main:app" || true
	@pkill -f "next dev" || true

docker-up:
	@docker compose up -d
	@echo "Backend: http://localhost:8000   Frontend: http://localhost:3000   Jaeger: http://localhost:16686"

docker-down:
	@docker compose down

docker-logs:
	@docker compose logs -f

docker-rebuild:
	@docker compose up -d --build

dev: docker-up

# Alembic (PostgreSQL). SQLite dev DBs are created by the app at startup.
migrate:
	@cd backend && ./venv/bin/python -m api.migrate

migrate-check:
	@cd backend && ./venv/bin/python -m api.migrate --check && ./venv/bin/alembic check

migrate-new:
	@test -n "$(m)" || (echo 'usage: make migrate-new m="describe the change"'; exit 2)
	@cd backend && ./venv/bin/alembic revision --autogenerate -m "$(m)"

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------
test: test-backend test-frontend

test-backend:
	@cd backend && ./venv/bin/python -m pytest -q

test-backend-pg:
	@test -n "$$DATABASE_URL" || (echo "set DATABASE_URL=postgresql://... to a scratch database"; exit 2)
	@cd backend && ./venv/bin/python -m api.migrate && ./venv/bin/python -m pytest -q

test-models:
	@cd backend && RAMPART_MODEL_TESTS=1 ./venv/bin/python -m pytest -q tests/test_injection_regression.py tests/test_policies_gliner.py

test-frontend:
	@cd frontend && npm test

lint:
	@cd frontend && npx eslint .

typecheck:
	@npx -y pyright
	@cd frontend && npx tsc --noEmit

audit:
	@echo "== backend"
	@cd backend && ./venv/bin/python -m pip_audit -r requirements.txt --no-deps
	@echo "== frontend"
	@cd frontend && npm audit --audit-level=high

eval-corpus:
	@cd backend && ./venv/bin/python eval/fetch_corpus.py

eval-gates:
	@cd backend && ./venv/bin/python eval/run_eval.py --profiles natural --gates

eval-smoke:
	@cd backend && ./venv/bin/python eval/run_eval.py --regex-only --profiles natural

# ---------------------------------------------------------------------------
# Production
# ---------------------------------------------------------------------------
deploy:
	@cd aws && ./update.sh

deploy-backend:
	@cd aws && ./update.sh --backend-only

deploy-frontend:
	@cd aws && ./update.sh --frontend-only

deploy-infra:
	@cd aws && ./deploy.sh

# Post-deploy verification; every line must print the expected code.
smoke:
	@B=$(PROD_URL)/api/v1; \
	chk() { code=$$(curl -s -o /dev/null -w '%{http_code}' "$$@"); printf '  %-42s %s\n' "$$1" "$$code"; }; \
	echo "Smoke: $(PROD_URL)"; \
	chk $$B/health; \
	chk $(PROD_URL)/; \
	chk $$B/auth/me                                      ; echo "    (expect 401)"; \
	chk $$B/auth/refresh -X POST -b rampart_session=x.y.z; echo "    (expect 403: CSRF header required)"; \
	chk $$B/auth/logout -X POST -H 'X-Requested-With: XMLHttpRequest'; echo "    (expect 204)"; \
	chk $$B/admin/stats                                  ; echo "    (expect 401)"; \
	chk $$B/filter/demo -X POST -H 'Content-Type: application/json' -d '{"content":"hi"}'; echo "    (expect 200 if playground enabled, 404 if disabled)"; \
	echo "  deployed image tags:"; \
	aws ecr describe-images --repository-name rampart-backend --region $${AWS_REGION:-us-west-2} --image-ids imageTag=latest --query 'imageDetails[0].imageTags' --output text | sed 's/^/    backend: /'; \
	aws ecr describe-images --repository-name rampart-frontend --region $${AWS_REGION:-us-west-2} --image-ids imageTag=latest --query 'imageDetails[0].imageTags' --output text | sed 's/^/    frontend: /'

# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------
clean:
	@find . -type d -name "__pycache__" -not -path "*/venv/*" -not -path "*/node_modules/*" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf backend/.pytest_cache frontend/.next frontend/out
	@echo "Clean complete!"

health-check:
	@curl -s http://localhost:8000/api/v1/health | python3 -m json.tool || echo "Backend not responding"
	@curl -s -o /dev/null -w "frontend: %{http_code}\n" http://localhost:3000 || echo "Frontend not responding"

prod-build:
	@cd backend && ./venv/bin/pip install -r requirements.txt
	@cd frontend && npm ci && npm run build

examples:
	@cd examples && python3 basic_usage.py
