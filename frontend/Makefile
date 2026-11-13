.PHONY: help install hooks dev build preview typecheck lint format format-check test check up down prod-up prod-mock-up prod-down logs prod-logs clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies and setup git hooks
	bun install --frozen-lockfile
	$(MAKE) hooks

hooks: ## Install Lefthook git hooks at repository root
	cd .. && ./frontend/node_modules/.bin/lefthook install

dev: ## Run local Vite dev server with Bun
	bun run dev

build: ## Typecheck and build production bundle
	bun run build

preview: ## Preview production build locally via Vite
	bun run preview

typecheck: ## Run TypeScript type checker (vue-tsc)
	bun run typecheck

lint: ## Run oxlint
	bun run lint

format: ## Fix oxlint issues and format code with oxfmt
	bun run lint:fix
	bun run format

format-check: ## Check formatting with oxfmt
	bun run format:check

test: ## Run unit tests with Vitest
	bun run test

check: ## Run typecheck, lint, format check, tests, and build
	bun run typecheck
	bun run lint
	bun run format:check
	bun run test
	bun run build

up: ## Start development Docker Compose (target: dev, Vite HMR on :5173)
	docker compose -f docker-compose.dev.yml up --build -d

down: ## Stop development Docker Compose
	docker compose -f docker-compose.dev.yml down

prod-up: ## Start production Docker Compose (target: prod, Caddy on :3000)
	docker compose -f docker-compose.prod.yml up --build -d

prod-mock-up: ## Start production Docker Compose with mock API enabled
	PROD_VITE_USE_MOCKS=true docker compose -f docker-compose.prod.yml up --build -d

prod-down: ## Stop production Docker Compose
	docker compose -f docker-compose.prod.yml down

logs: ## View dev container logs
	docker compose -f docker-compose.dev.yml logs -f frontend

prod-logs: ## View prod container logs
	docker compose -f docker-compose.prod.yml logs -f frontend

clean: ## Remove build artifacts and caches
	rm -rf dist dist-ssr *.tsbuildinfo node_modules/.vite
