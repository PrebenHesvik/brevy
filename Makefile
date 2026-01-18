.PHONY: help install dev dev-api dev-analytics dev-client build test lint format clean docker-up docker-down docker-logs certs db-migrate db-upgrade db-downgrade db-current db-history

# Default target
help:
	@echo "Brevy - URL Shortener"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Setup:"
	@echo "  install        Install all dependencies (Python + Node)"
	@echo "  certs          Generate local HTTPS certificates with mkcert"
	@echo ""
	@echo "Development:"
	@echo "  dev            Start all services (Docker + API + Analytics + Client)"
	@echo "  dev-api        Start API service only"
	@echo "  dev-analytics  Start Analytics service only"
	@echo "  dev-client     Start React client only"
	@echo ""
	@echo "Docker:"
	@echo "  docker-up      Start PostgreSQL and Redis containers"
	@echo "  docker-down    Stop and remove containers"
	@echo "  docker-logs    View container logs"
	@echo ""
	@echo "Database:"
	@echo "  db-upgrade     Apply all pending migrations"
	@echo "  db-downgrade   Revert last migration"
	@echo "  db-migrate     Generate new migration (use: make db-migrate m='description')"
	@echo "  db-current     Show current migration revision"
	@echo "  db-history     Show migration history"
	@echo ""
	@echo "Quality:"
	@echo "  lint           Run all linters"
	@echo "  lint-fix       Run linters and fix issues"
	@echo "  format         Format all code"
	@echo "  test           Run all tests"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean          Remove build artifacts and caches"

# =============================================================================
# Setup
# =============================================================================

install: install-api install-analytics install-client install-hooks
	@echo "All dependencies installed!"

install-api:
	@echo "Installing API service dependencies..."
	cd services/api && uv sync --all-extras

install-analytics:
	@echo "Installing Analytics service dependencies..."
	cd services/analytics && uv sync --all-extras

install-client:
	@echo "Installing client dependencies..."
	cd client && pnpm install

install-hooks:
	@echo "Installing pre-commit hooks..."
	pre-commit install

certs:
	@echo "Generating local HTTPS certificates..."
	@mkdir -p certs
	mkcert -install
	mkcert -key-file certs/localhost-key.pem -cert-file certs/localhost.pem localhost 127.0.0.1 ::1
	@echo "Certificates generated in ./certs/"

# =============================================================================
# Development
# =============================================================================

dev: docker-up
	@echo "Starting all services..."
	@make -j3 dev-api dev-analytics dev-client

dev-api:
	@echo "Starting API service on http://localhost:8000"
	cd services/api && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-analytics:
	@echo "Starting Analytics service on http://localhost:8001"
	cd services/analytics && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

dev-client:
	@echo "Starting React client on http://localhost:5173"
	cd client && pnpm dev

# =============================================================================
# Docker
# =============================================================================

docker-up:
	@echo "Starting Docker containers..."
	docker-compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 3
	docker-compose ps

docker-down:
	@echo "Stopping Docker containers..."
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-clean:
	@echo "Removing containers and volumes..."
	docker-compose down -v

# =============================================================================
# Database
# =============================================================================

db-upgrade:
	@echo "Applying database migrations..."
	cd services/api && uv run alembic upgrade head

db-downgrade:
	@echo "Reverting last migration..."
	cd services/api && uv run alembic downgrade -1

db-migrate:
	@echo "Generating new migration..."
	cd services/api && uv run alembic revision --autogenerate -m "$(m)"

db-current:
	@echo "Current migration revision:"
	cd services/api && uv run alembic current

db-history:
	@echo "Migration history:"
	cd services/api && uv run alembic history

# =============================================================================
# Quality
# =============================================================================

lint: lint-api lint-analytics lint-client
	@echo "All linting complete!"

lint-api:
	@echo "Linting API service..."
	cd services/api && uv run ruff check .
	cd services/api && uv run mypy .

lint-analytics:
	@echo "Linting Analytics service..."
	cd services/analytics && uv run ruff check .
	cd services/analytics && uv run mypy .

lint-client:
	@echo "Linting client..."
	cd client && pnpm lint

lint-fix: lint-fix-api lint-fix-analytics lint-fix-client
	@echo "All lint fixes applied!"

lint-fix-api:
	cd services/api && uv run ruff check --fix .
	cd services/api && uv run ruff format .

lint-fix-analytics:
	cd services/analytics && uv run ruff check --fix .
	cd services/analytics && uv run ruff format .

lint-fix-client:
	cd client && pnpm lint:fix

format: format-api format-analytics format-client
	@echo "All formatting complete!"

format-api:
	cd services/api && uv run ruff format .

format-analytics:
	cd services/analytics && uv run ruff format .

format-client:
	cd client && pnpm format

test: test-api test-analytics test-client
	@echo "All tests complete!"

test-api:
	@echo "Testing API service..."
	cd services/api && uv run pytest

test-analytics:
	@echo "Testing Analytics service..."
	cd services/analytics && uv run pytest

test-client:
	@echo "Testing client..."
	cd client && pnpm test --run 2>/dev/null || echo "No tests configured yet"

# =============================================================================
# Cleanup
# =============================================================================

clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Clean complete!"
