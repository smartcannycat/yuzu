"""Shared async Gemini SDK runner managing clients, cooldowns, and key failover."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError

from ml_service.domains.entities import ModelAttemptEntity
from ml_service.infrastructure.gemini_hedging import (
    is_non_retryable_client_error,
    run_hedged_chain,
)
from ml_service.infrastructure.key_pool import GeminiKeyPool

logger = logging.getLogger(__name__)

__all__ = ["GeminiRunner", "is_non_retryable_client_error"]


class GeminiRunner[T]:
    """Manages google-genai async clients, model cooldowns, key failover, and hedged execution."""

    def __init__(
        self,
        key_pool: GeminiKeyPool,
        flash_model: str = "gemini-3.6-flash",
        fallback_models: list[str] | None = None,
        *,
        request_timeout_ms: int = 25000,
        sdk_max_attempts: int = 1,
        model_cooldown_seconds: float = 120.0,
        client_error_cooldown_seconds: float = 300.0,
        key_cooldown_seconds: float = 30.0,
        max_key_tries: int = 3,
        request_deadline_seconds: float = 45.0,
        hedge_delay_seconds: float = 8.0,
    ) -> None:
        self.key_pool = key_pool
        self.flash_model = flash_model
        self.request_timeout_ms = request_timeout_ms
        self.sdk_max_attempts = sdk_max_attempts
        self.model_cooldown_seconds = model_cooldown_seconds
        self.client_error_cooldown_seconds = client_error_cooldown_seconds
        self.key_cooldown_seconds = key_cooldown_seconds
        self.max_key_tries = max_key_tries
        self.request_deadline_seconds = request_deadline_seconds
        self.hedge_delay_seconds = hedge_delay_seconds

        chain = [flash_model, *(fallback_models or [])]
        seen: set[str] = set()
        self._model_chain: list[str] = []
        for model_name in chain:
            cleaned = model_name.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                self._model_chain.append(cleaned)

        self._model_cooldown_until: dict[str, float] = {}
        self._clients: dict[str, Any] = {}

    @property
    def model_chain(self) -> tuple[str, ...]:
        """Return configured model priority chain."""
        return tuple(self._model_chain)

    def get_client(self, api_key: str) -> Any:
        """Return cached genai.Client per API key with explicit timeout and retry caps."""
        client = self._clients.get(api_key)
        if client is None:
            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(
                    api_version="v1beta",
                    timeout=self.request_timeout_ms,
                    retry_options=types.HttpRetryOptions(attempts=self.sdk_max_attempts),
                ),
            )
            self._clients[api_key] = client
        return client

    def set_client(self, api_key: str, client: Any) -> None:
        """Register or replace a client instance for a key (useful in tests)."""
        self._clients[api_key] = client

    def ordered_candidate_models(self) -> list[str]:
        """Return healthy models in priority order, then cooled-down models by earliest expiry."""
        now = time.monotonic()
        healthy: list[str] = []
        cooled: list[tuple[float, str]] = []
        for model_name in self._model_chain:
            until = self._model_cooldown_until.get(model_name, 0.0)
            if until <= now:
                healthy.append(model_name)
            else:
                cooled.append((until, model_name))
        cooled.sort(key=lambda item: item[0])
        return [*healthy, *(name for _, name in cooled)]

    def mark_model_cooldown(self, model_name: str, duration_seconds: float) -> None:
        """Place a model on temporary cooldown."""
        if duration_seconds > 0:
            self._model_cooldown_until[model_name] = time.monotonic() + duration_seconds

    def is_model_cooled_down(self, model_name: str) -> bool:
        """Return True when the model is currently in cooldown."""
        return self._model_cooldown_until.get(model_name, 0.0) > time.monotonic()

    def clear_model_cooldowns(self) -> None:
        """Clear all model cooldown entries."""
        self._model_cooldown_until.clear()

    async def aclose(self) -> None:
        """Close all cached async and sync google-genai SDK clients cleanly."""
        clients = list(self._clients.values())
        self._clients.clear()
        for client in clients:
            aio = getattr(client, "aio", None)
            aclose_fn = getattr(aio, "aclose", None)
            if callable(aclose_fn):
                try:
                    await aclose_fn()
                except (OSError, RuntimeError) as exc:
                    logger.debug("Error closing Gemini async client: %s", exc)
            close_fn = getattr(client, "close", None)
            if callable(close_fn):
                try:
                    close_fn()
                except (OSError, RuntimeError) as exc:
                    logger.debug("Error closing Gemini sync client: %s", exc)

    async def generate_content(
        self,
        *,
        api_key: str,
        model_name: str,
        contents: Any,
        config: types.GenerateContentConfig,
    ) -> Any:
        """Execute an async generate_content call via client.aio."""
        client = self.get_client(api_key)
        return await client.aio.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )

    async def run_decisions(
        self,
        *,
        api_key: str,
        payload: dict[str, Any],
    ) -> Any:
        """Execute an async Decisions API gatekeeper call via client.aio."""
        client = self.get_client(api_key)
        aio = getattr(client, "aio", None)
        decisions_api = getattr(aio, "decisions", None)
        if decisions_api is None:
            raise RuntimeError("Gemini SDK client.aio.decisions is unavailable.")
        return await asyncio.wait_for(
            decisions_api.create(**payload),
            timeout=self.request_timeout_ms / 1000.0,
        )

    async def call_with_thinking_downgrade(
        self,
        *,
        model_name: str,
        api_key: str,
        configured_level: types.ThinkingLevel,
        invoke: Callable[[str, str, types.ThinkingLevel], Awaitable[T]],
    ) -> T:
        """Invoke a model call and retry at LOW when it rejects a non-LOW thinking level."""
        try:
            return await invoke(model_name, api_key, configured_level)
        except ClientError as exc:
            status_code = getattr(exc, "code", None)
            if (
                status_code == 400
                and "Thinking level" in str(exc)
                and configured_level != types.ThinkingLevel.LOW
            ):
                logger.warning(
                    "Model %s rejected %s; downgrading ThinkingLevel to LOW.",
                    model_name,
                    configured_level,
                )
                return await invoke(model_name, api_key, types.ThinkingLevel.LOW)
            raise

    async def _call_with_thinking_downgrade(
        self,
        *,
        model_name: str,
        api_key: str,
        configured_level: types.ThinkingLevel,
        invoke: Callable[[str, str, types.ThinkingLevel], Awaitable[T]],
    ) -> T:
        return await self.call_with_thinking_downgrade(
            model_name=model_name,
            api_key=api_key,
            configured_level=configured_level,
            invoke=invoke,
        )

    async def try_model_with_keys(
        self,
        *,
        model_name: str,
        configured_level: types.ThinkingLevel,
        attempts: list[ModelAttemptEntity],
        invoke: Callable[[str, str, types.ThinkingLevel], Awaitable[T]],
    ) -> T:
        """Run one model across up to max_key_tries API keys with cooldown handling."""
        max_tries = (
            max(1, min(self.key_pool.key_count, self.max_key_tries))
            if self.key_pool.key_count > 1
            else 1
        )
        last_exc: Exception | None = None

        for key_attempt in range(max_tries):
            t0 = time.perf_counter()
            async with self.key_pool.acquire() as api_key:
                try:
                    result = await self._call_with_thinking_downgrade(
                        model_name=model_name,
                        api_key=api_key,
                        configured_level=configured_level,
                        invoke=invoke,
                    )
                    attempts.append(
                        ModelAttemptEntity(
                            model=model_name,
                            status="ok",
                            ms=int((time.perf_counter() - t0) * 1000),
                        )
                    )
                    return result
                except ClientError as exc:
                    last_exc = exc
                    should_retry_key = self._handle_client_error(
                        exc,
                        model_name=model_name,
                        api_key=api_key,
                        attempt_ms=int((time.perf_counter() - t0) * 1000),
                        key_attempt=key_attempt,
                        max_tries=max_tries,
                        attempts=attempts,
                    )
                    if should_retry_key:
                        continue
                    break
                except (
                    ServerError,
                    TimeoutError,
                    ValueError,
                    httpx.TimeoutException,
                    httpx.TransportError,
                ) as exc:
                    last_exc = exc
                    self._handle_transient_error(
                        exc,
                        model_name=model_name,
                        attempt_ms=int((time.perf_counter() - t0) * 1000),
                        attempts=attempts,
                    )
                    break

        assert last_exc is not None
        raise last_exc

    def _handle_client_error(
        self,
        exc: ClientError,
        *,
        model_name: str,
        api_key: str,
        attempt_ms: int,
        key_attempt: int,
        max_tries: int,
        attempts: list[ModelAttemptEntity],
    ) -> bool:
        status_code = getattr(exc, "code", None)
        if status_code == 429:
            attempts.append(ModelAttemptEntity(model=model_name, status="error_429", ms=attempt_ms))
            self.key_pool.mark_key_rate_limited(api_key, self.key_cooldown_seconds)
            logger.warning(
                "Model %s rate-limited key (429), attempt %s/%s.",
                model_name,
                key_attempt + 1,
                max_tries,
            )
            if key_attempt + 1 < max_tries:
                return True
            self.mark_model_cooldown(model_name, self.model_cooldown_seconds)
            return False

        if status_code in (400, 404):
            attempts.append(
                ModelAttemptEntity(model=model_name, status=f"error_{status_code}", ms=attempt_ms)
            )
            logger.warning("Model %s rejected request (%s); putting on cooldown.", model_name, exc)
            self.mark_model_cooldown(model_name, self.client_error_cooldown_seconds)
            return False

        attempts.append(
            ModelAttemptEntity(
                model=model_name,
                status=f"error_{status_code or 'client'}",
                ms=attempt_ms,
            )
        )
        raise exc

    def _handle_transient_error(
        self,
        exc: Exception,
        *,
        model_name: str,
        attempt_ms: int,
        attempts: list[ModelAttemptEntity],
    ) -> None:
        status_code = getattr(exc, "code", None)
        status_label = f"error_{status_code}" if status_code else f"error_{exc.__class__.__name__}"
        attempts.append(ModelAttemptEntity(model=model_name, status=status_label, ms=attempt_ms))
        logger.warning(
            "Model %s failed transiently (%s); switching to next fallback model.",
            model_name,
            exc,
        )
        self.mark_model_cooldown(model_name, self.model_cooldown_seconds)

    async def run_hedged(
        self,
        *,
        run_model: Callable[[str], Awaitable[T]],
        attempts: list[ModelAttemptEntity],
        extract_t0: float,
    ) -> T:
        """Run ordered candidate models with deadline, fail-fast 401/403, and hedging."""
        return await run_hedged_chain(
            self,
            run_model=run_model,
            attempts=attempts,
            extract_t0=extract_t0,
        )
