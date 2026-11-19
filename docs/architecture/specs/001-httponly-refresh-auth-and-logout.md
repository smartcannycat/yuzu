# 001: HttpOnly Refresh Cookie Authentication, Logout, and Account Rate Limiting

- **Status:** Approved
- **Services affected:** backend, frontend

## Problem & Goal
Persisting `refresh_token` in browser `localStorage` (`FE-SEC-02`) exposes long-lived credentials to XSS payloads, while the absence of a logout endpoint prevents server-side refresh token revocation upon sign-out (`BE-SEC-08`). In addition, login rate limiting keyed solely by `client_ip:email` allows distributed credential-stuffing attacks across rotating IP addresses and leaks plaintext email addresses into Redis keys (`BE-SEC-09`). This specification moves `refresh_token` to a scoped `HttpOnly` cookie, keeps `access_token` strictly in JavaScript memory, adds cookie-based `POST /api/v1/auth/logout` with CSRF/origin validation, and introduces an IP-independent per-account login rate limit keyed by email hash.

## Contract & Domain Invariants

- **Refresh Cookie Transport (`FE-SEC-02`):**
  - Cookie name: `yuzu_refresh_token` (`JWT_REFRESH_COOKIE_NAME = "yuzu_refresh_token"`).
  - Cookie attributes: `HttpOnly=True`, `Secure=not settings.DEBUG`, `SameSite="Lax"` (`JWT_REFRESH_COOKIE_SAMESITE = "Lax"`), `Path=/api/v1/auth/` (`JWT_REFRESH_COOKIE_PATH = "/api/v1/auth/"`), and `max_age=int(jwt_settings.REFRESH_TOKEN_LIFETIME.total_seconds())`.
  - `CORS_ALLOW_CREDENTIALS = True` in `backend/config/settings/base.py` so credentialed browser requests can receive and send the cookie.
  - Set on `POST /api/v1/auth/register` (`201`), `POST /api/v1/auth/login` (`200`), and `POST /api/v1/auth/refresh` (`200`).
- **Response Schemas & In-Memory Access Token:**
  - `AuthTokensResponse` omits `refresh_token` and exposes only `{ access_token, token_type, expires_in_sec, user }`.
  - `TokenRefreshRequest` is removed; `POST /api/v1/auth/refresh` takes no JSON request body and reads `request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)`.
  - Frontend holds `access_token` strictly in JavaScript memory (no `localStorage` or `sessionStorage` token storage), sends `credentials: "include"` on auth requests, and silently restores sessions on reload via `POST /api/v1/auth/refresh`.
- **Rotation & Logout Revocation (`BE-SEC-08`):**
  - `POST /api/v1/auth/refresh` (`200: AuthTokensResponse`; `401`, `403`, `429` `ProblemDetail`) validates the cookie token, verifies the active user exists, blacklists the consumed token (`ROTATE_REFRESH_TOKENS = True`, `BLACKLIST_AFTER_ROTATION = True`), and sets a newly rotated `yuzu_refresh_token` cookie. Missing, invalid, expired, or blacklisted cookies return `401` `application/problem+json`.
  - `POST /api/v1/auth/logout` (`204: None`; `403` `ProblemDetail` on origin/CSRF failure) enforces the CSRF/origin guard, blacklists the cookie refresh token via `ninja_jwt.token_blacklist` (`RefreshToken(raw).blacklist()`) if present and valid, and deletes the `yuzu_refresh_token` cookie (`Path=/api/v1/auth/`, `SameSite=Lax`). Logout is idempotent and returns `204` even if the cookie is missing, expired, or already blacklisted.
- **CSRF / Origin Protection on Cookie Endpoints:**
  - Both `POST /api/v1/auth/refresh` and `POST /api/v1/auth/logout` enforce same-origin validation before processing the cookie.
  - A request is allowed only when `Origin` (or `Referer` origin fallback when `Origin` is absent) matches `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, or the request's own scheme and host (`request.get_host()`), **or** when the `X-Requested-With: YuzuSPA` header is present.
  - Any mismatch or missing signal returns `403` `application/problem+json` (`ProblemDetail`). The frontend SPA attaches `X-Requested-With: YuzuSPA` on auth requests.
- **Per-Account Login Rate Limiting (`BE-SEC-09`):**
  - `POST /api/v1/auth/login` keeps IP throttling (`auth:login:ip`, `limit=40`, `window_sec=60`) and adds a pure IP-independent per-account limit (`auth:login:email`, `limit=10`, `window_sec=60`) keyed by `hashlib.sha256(normalized_email.encode()).hexdigest()`, returning `429` `application/problem+json` when exceeded without storing plaintext email addresses in Redis keys.

## Verification Plan
- **Backend (`backend/tests/test_auth.py`):** Verify `register`, `login`, and `refresh` omit `refresh_token` from JSON and set `yuzu_refresh_token` with `HttpOnly`, `Path=/api/v1/auth/`, `SameSite=Lax`, and `Secure=not DEBUG`; verify token rotation and blacklisting on `refresh`; verify `logout` returns `204`, clears the cookie, and prevents reuse of the revoked token; verify `403 ProblemDetail` on cross-origin requests lacking `X-Requested-With: YuzuSPA`; verify `429 ProblemDetail` on per-account login throttling across varying client IPs.
- **Frontend (`frontend/src/api/httpClient.test.ts`, `frontend/src/stores/auth.test.ts`):** Verify no `localStorage`/`sessionStorage` token storage, `credentials: "include"` and `X-Requested-With: YuzuSPA` headers on auth endpoints, silent refresh recovery, and `POST /api/v1/auth/logout` execution on sign-out.
- **Contract Sync:** Run `make openapi` and verify `make check-contracts` passes cleanly.
