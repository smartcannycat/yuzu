# 004: Background Pipeline Throughput Optimization & Multi-Proxy Scraping

- **Status:** Approved
- **Services affected:** backend, ml_service, infra

## Problem & Goal
Even with paid Gemini quotas and multi-proxy scraper pools, processing high-volume batches (e.g., 100 auction sheets during business pilots) hits structural throughput bottlenecks in the background pipeline: `run_batch_pipeline` executes items strictly sequentially one at a time, `_advance_step()` sleeps `0.2s` per step, Celery runs `--pool=prefork --concurrency=4`, `AleadoClient` re-authenticates per lot without cross-lot cookie reuse or Redis caching and runs chassis OCR sequentially, Drom/Farpost execute internal sub-queries sequentially even when multiple proxies are configured, and `ml_service` defaults (`120`/`300` req/min) would throttle burst worker concurrency. Converting synchronous Django Ninja CRUD endpoints to ASGI `async def` yields no improvement because Django 6.1 ORM runs synchronously underneath (`sync_to_async`) and `api` performs no external HTTP requests. Instead, scaling concurrent I/O execution inside the background Celery pipeline eliminates real latency while keeping Granian WSGI, REST/OpenAPI contracts, and `BE-BLK-01` lease guarantees intact.

## Contract & Domain Invariants
- **No REST / OpenAPI / Schema Changes:**
  - `docs/architecture/openapi.json`, `frontend/src/types/api.generated.ts`, and Django database schemas/migrations remain completely unchanged.
- **Bounded Batch Parallelism & Celery Threads Pool:**
  - `run_batch_pipeline` claims and processes up to `PIPELINE_BATCH_ITEM_CONCURRENCY` (`4` default in `[pipeline]`, range `1..16`) items concurrently via a bounded `ThreadPoolExecutor`, isolating unexpected per-item exceptions so healthy sibling items in the same batch continue and dynamically appended `QUEUED` items are drained before batch finalization.
  - `_claim_next_queued_item` uses `select_for_update(skip_locked=True)` and `_PIPELINE_STEP_DELAY_SEC` is set to `0.0` (symbol preserved for test compatibility).
  - Celery worker containers switch to `--pool=threads --concurrency=4` (`docker-compose.yml`, `docker-compose.prod.yml`) and `2` in `docker-compose.override.yml`, supporting up to 16 concurrent items in one worker process with low memory overhead.
  - Every worker thread and periodic Celery task releases PostgreSQL connections (`connection.close()`) in `finally` blocks and prior to long network waits (`ml_service` OCR / parallel enrichment wait / coordinator wait).
- **Aleado Session Sharing, 3-Tier Redis Cache, OCR Overlap & Soft Budget:**
  - `AleadoClient` maintains an in-process thread-safe cookie store and single-flight login lock keyed by `(base_url, username)` (no credentials or cookies written to Redis; disabled by default when custom HTTP transports are injected for test isolation).
  - `AleadoCache` stores read-through entries in Redis under `yuzu:aleado:{search,detail,chassis}:*` (default TTLs: 30m search, 7d detail, 30d non-empty verified frame ID) and fails open on Redis errors.
  - Candidate verification overlaps Aleado HTTP fetches with bounded concurrent `ml_client.read_chassis` OCR (`ALEADO_OCR_MAX_WORKERS = 3`), respects a soft per-lot budget (`ALEADO_BUDGET_SEC = 25.0`) while checking highest-priority candidates first, and preserves deterministic candidate ordering.
- **Multi-Proxy Parallelism in Drom & Farpost (Thread-Safe Client Isolation):**
  - Because `ResilientHttpSession` / `curl_cffi.Session` instances are not thread-safe across threads, `DromMarketService` (`power_resolver` + market cascade) and `Farpost` (`estimate_repair` replacement panels) spawn isolated per-worker client instances (sharing the Redis `ProxyPool` and per-`(domain, proxy_key)` throttle slots) whenever multiple proxies (`len(SCRAPER_PROXY_URLS) > 1`) or an explicit client factory are active, preserving deterministic result order.
- **ML Service Internal Rate-Limit Headroom:**
  - `ml_service/config.toml` and `ml_service/config.py` raise internal service defaults to `rate_limit_requests_per_minute = 600` and `pre_auth_rate_limit_requests_per_minute = 1200` so 16 concurrent workers + Aleado `read_chassis` calls are not self-rejected with HTTP 429 on `ml_internal` (Gemini upstream quotas remain governed by `GeminiKeyPool`).

## Verification Plan
- **Backend (`backend/tests/test_pipeline_throughput.py`):** Verify config defaults/bounds and `_PIPELINE_STEP_DELAY_SEC == 0.0`, concurrent batch item execution with crash isolation and dynamic item pickup (`Barriers`), single-flight Aleado shared login & re-auth, 3-tier Aleado Redis cache hit shortcuts & fail-open behavior, concurrent Aleado chassis OCR overlap + soft time budget, and isolated-client parallel Drom power+cascade and Farpost replacement panels with deterministic output ordering.
- **Backend & ML Full Suites + Boundary Checks:** Run `ruff check`, `ruff format --check`, `lint-imports`, `makemigrations --check --dry-run`, `export_openapi --check`, full backend & ML `pytest` suites, `scripts/check_architecture.py`, Compose config checks, and a live Celery `--pool=threads` worker startup smoke test against Redis.
