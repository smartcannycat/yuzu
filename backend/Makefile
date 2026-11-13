.PHONY: help install hooks dev migrate makemigrations createsuperuser test lint format check up up-db down prod-up prod-down logs clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies and setup git hooks
	uv sync
	cd .. && uv --project backend run lefthook install

hooks: ## Install Lefthook git hooks at repository root
	cd .. && uv --project backend run lefthook install

dev: ## Run development ASGI server (Granian) with reload
	uv run granian --interface asginl config.asgi:application --reload --host 127.0.0.1 --port 8000

migrate: ## Apply database migrations
	uv run python manage.py migrate

makemigrations: ## Generate database migrations
	uv run python manage.py makemigrations

createsuperuser: ## Create Django superuser
	uv run python manage.py createsuperuser

test: ## Run tests with pytest
	uv run pytest

lint: ## Check lint errors with Ruff
	uv run ruff check .

format: ## Format code with Ruff
	uv run ruff format .
	uv run ruff check --fix .

check: ## Run lint, format check and tests
	uv run ruff check .
	uv run ruff format --check .
	uv run pytest

up: ## Start development Docker Compose (target: dev)
	docker compose -f docker-compose.dev.yml up --build -d

up-db: ## Start only PostgreSQL container for local dev and tests
	docker compose -f docker-compose.dev.yml up -d db

down: ## Stop development Docker Compose
	docker compose -f docker-compose.dev.yml down

prod-up: ## Start production Docker Compose (target: prod)
	docker compose -f docker-compose.prod.yml up --build -d

prod-down: ## Stop production Docker Compose
	docker compose -f docker-compose.prod.yml down

logs: ## View API container logs
	docker compose -f docker-compose.dev.yml logs -f api

clean: ## Clean cache and temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
