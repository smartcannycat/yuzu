# Yuzu Frontend

Web application for Yuzu built with Vue 3, TypeScript, Vite, Tailwind CSS v4, Vue Router, Pinia, oxlint, oxfmt, and Bun.

## Tech Stack

Vue 3, TypeScript, Vite, Tailwind CSS v4, Vue Router, Pinia, Vue DevTools, Vitest, oxlint, oxfmt, Lefthook, Bun, Caddy.

## Quick Start (Local)

```bash
cp .env.example .env
make install
make dev
```

The dev server will be available at `http://127.0.0.1:5173`.

## Docker Compose

Development (Bun + Vite HMR on `127.0.0.1:5173`):

```bash
make up
```

Production build served by Caddy (HTTP on `127.0.0.1:3000`, behind external Traefik TLS in deployment):

```bash
make prod-up
```

Production build with mock API enabled (standalone preview without backend):

```bash
make prod-mock-up
```

Caddy listens on HTTP only (`auto_https off`), trusts private-range proxy headers from Traefik, serves static assets from `/srv` (`immutable` cache for `/assets/*`, `no-cache` for SPA fallback `/index.html`), exposes `/healthz`, and proxies `/api/*` to `API_UPSTREAM` (default `http://host.docker.internal:8000` in standalone compose, `http://api:8000` in `Caddyfile`). If `SITE_ADDRESS` is customized with a hostname, keep the `http://` scheme so Caddy stays HTTP-only behind Traefik, and set `HEALTHCHECK_HOST` to match. Note that `/media/*` is expected to be routed by Traefik or backend Nginx.

## Commands

- `make help` - List available Makefile targets
- `make install` - Install dependencies with Bun and setup Lefthook
- `make hooks` - Install Lefthook git hooks at repository root
- `make dev` - Start local Vite dev server
- `make build` - Typecheck and build production bundle
- `make preview` - Preview production build locally
- `make typecheck` - Run `vue-tsc`
- `make lint` - Run `oxlint`
- `make format` - Fix `oxlint` issues and format code with `oxfmt`
- `make format-check` - Check formatting with `oxfmt`
- `make test` - Run unit tests with Vitest
- `make check` - Run typecheck, lint, format check, tests, and build
- `make up` / `make down` - Manage dev Docker Compose
- `make prod-up` / `make prod-down` - Manage prod Docker Compose
- `make prod-mock-up` - Start prod Docker Compose with `PROD_VITE_USE_MOCKS=true`
- `make logs` / `make prod-logs` - View dev or prod container logs
- `make clean` - Remove build artifacts and Vite caches
