.PHONY: help openapi check-contracts check-architecture check up down prod-up prod-down logs

help: ## Show repository-level commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

openapi: ## Export backend OpenAPI schema and regenerate frontend TypeScript types
	cd backend && uv run python -m config.openapi
	cd frontend && bun run gen:api

check-contracts: ## Verify docs/architecture/openapi.json and api.generated.ts match backend schemas
	cd backend && uv run python -m config.openapi --check
	cd frontend && bun run check:api

check-architecture: ## Run backend, ML service, and frontend architecture boundary checks
	cd backend && uv run lint-imports
	python3 scripts/check_architecture.py

check: check-contracts check-architecture ## Run contract, architecture, backend, ML, and frontend checks
	$(MAKE) -C backend check
	$(MAKE) -C ml_service check
	$(MAKE) -C frontend check

up: ## Start full development Docker Compose stack
	docker compose up --build -d

down: ## Stop development Docker Compose stack
	docker compose down

prod-up: ## Start production Docker Compose stack
	docker compose -f docker-compose.prod.yml up --build -d

prod-down: ## Stop production Docker Compose stack
	docker compose -f docker-compose.prod.yml down

logs: ## Follow Docker Compose logs
	docker compose logs -f
