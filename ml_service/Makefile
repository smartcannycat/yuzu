.PHONY: help install hooks dev test cov lint format check up down logs clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies with uv and setup git hooks
	uv sync
	cd "$$(git rev-parse --show-toplevel)" && uv --project ml_service run lefthook install

hooks: ## Install Lefthook git hooks at repository root
	cd "$$(git rev-parse --show-toplevel)" && uv --project ml_service run lefthook install

dev: ## Run development FastAPI server with reload
	uv run uvicorn ml_service.main:app --host 127.0.0.1 --port 8001 --reload

test: ## Run offline test suite with pytest
	uv run pytest

cov: ## Run test suite with coverage report
	uv run pytest --cov=ml_service --cov-report=term-missing

lint: ## Check lint errors with Ruff
	uv run ruff check .

format: ## Format code and fix lint issues with Ruff
	uv run ruff format .
	uv run ruff check --fix .

check: ## Run Ruff lint, format check, and pytest
	uv run ruff check .
	uv run ruff format --check .
	uv run pytest

up: ## Start standalone ML service Docker Compose
	docker compose up --build -d

down: ## Stop standalone ML service Docker Compose
	docker compose down

logs: ## View standalone ML service container logs
	docker compose logs -f ml

clean: ## Clean cache and temporary files
	find . -path './.venv' -prune -o -type d -name "__pycache__" -exec rm -rf {} +
	find . -path './.venv' -prune -o -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov
