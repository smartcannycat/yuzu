# ==========================================
# Stage 1: Base image with Bun
# ==========================================
FROM oven/bun:1.4.4-alpine AS base

WORKDIR /app

# ==========================================
# Stage 2: Dependencies installation
# ==========================================
FROM base AS deps

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile --ignore-scripts

# ==========================================
# Stage 3: Development target (Vite HMR)
# ==========================================
FROM deps AS dev

COPY . .

EXPOSE 5173

CMD ["bun", "run", "dev", "--host", "0.0.0.0", "--port", "5173"]

# ==========================================
# Stage 4: Production builder
# ==========================================
FROM deps AS prod-builder

ARG VITE_API_BASE_URL=/api/v1
ARG VITE_USE_MOCKS=false

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_USE_MOCKS=${VITE_USE_MOCKS}

COPY . .
RUN bun run build

# ==========================================
# Stage 5: Production target (Caddy static + reverse proxy)
# ==========================================
FROM caddy:2.11.9-alpine AS prod

COPY docker/Caddyfile /etc/caddy/Caddyfile
COPY --from=prod-builder /app/dist /srv

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=5s \
    CMD [ "$(wget -qO- http://127.0.0.1:80/healthz)" = "OK" ] || exit 1

CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
