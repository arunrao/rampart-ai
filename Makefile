.PHONY: help setup install start stop test clean docker-up docker-down

help:
	@echo "Project Rampart - Available Commands"
	@echo "===================================="
	@echo "setup          - Run initial setup script"
	@echo "install        - Install all dependencies"
	@echo "start          - Start backend and frontend"
	@echo "stop           - Stop all services"
	@echo "test           - Run all tests"
	@echo "test-backend   - Run backend tests"
	@echo "test-frontend  - Run frontend tests"
	@echo "clean          - Clean build artifacts"
	@echo "docker-up      - Start with Docker Compose"
	@echo "docker-down    - Stop Docker Compose"
	@echo "docker-logs    - View Docker logs"
	@echo "format         - Format code"
	@echo "lint           - Lint code"

setup:
	@echo "Running setup script..."
	@./setup.sh

install:
	@echo "Installing backend dependencies..."
	@cd backend && python -m venv venv && . venv/bin/activate && pip install -r requirements.txt
	@echo "Installing frontend dependencies..."
	@cd frontend && npm install

start:
	@echo "Starting Project Rampart..."
	@echo "Backend will run on http://localhost:8000"
	@echo "Frontend will run on http://localhost:3000"
	@make -j2 start-backend start-frontend

start-backend:
	@cd backend && . venv/bin/activate && uvicorn api.main:app --reload

start-frontend:
	@cd frontend && npm run dev

stop:
	@echo "Stopping services..."
	@pkill -f "uvicorn api.main:app" || true
	@pkill -f "next dev" || true

test:
	@make test-backend
	@make test-frontend

test-backend:
	@echo "Running backend tests..."
	@cd backend && . venv/bin/activate && pytest tests/ -v

test-frontend:
	@echo "Running frontend tests..."
	@cd frontend && npm test

clean:
	@echo "Cleaning build artifacts..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf backend/.pytest_cache 2>/dev/null || true
	@rm -rf frontend/.next 2>/dev/null || true
	@rm -rf frontend/out 2>/dev/null || true
	@echo "Clean complete!"

docker-up:
	@echo "Starting with Docker Compose..."
	@docker-compose up -d
	@echo "Services started!"
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:3000"

docker-down:
	@echo "Stopping Docker Compose..."
	@docker-compose down

docker-logs:
	@docker-compose logs -f

docker-rebuild:
	@echo "Rebuilding Docker images..."
	@docker-compose up -d --build

format:
	@echo "Formatting backend code..."
	@cd backend && . venv/bin/activate && black . || echo "Install black: pip install black"
	@echo "Formatting frontend code..."
	@cd frontend && npm run format || echo "Add format script to package.json"

lint:
	@echo "Linting backend code..."
	@cd backend && . venv/bin/activate && flake8 . || echo "Install flake8: pip install flake8"
	@echo "Linting frontend code..."
	@cd frontend && npm run lint

dev:
	@make docker-up

prod-build:
	@echo "Building for production..."
	@cd backend && . venv/bin/activate && pip install -r requirements.txt
	@cd frontend && npm install && npm run build

health-check:
	@echo "Checking backend health..."
	@curl -s http://localhost:8000/api/v1/health | python -m json.tool || echo "Backend not responding"
	@echo "\nChecking frontend..."
	@curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 || echo "Frontend not responding"

examples:
	@echo "Running example scripts..."
	@cd examples && python basic_usage.py
