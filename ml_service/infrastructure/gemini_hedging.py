"""Hedged multi-model execution and fail-fast cancellation helpers for GeminiRunner."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Protocol

import httpx
from google.genai.errors import ClientError, ServerError

from ml_service.domains.entities import ModelAttemptEntity


class HedgedRunnerHost(Protocol):
    model_chain: tuple[str, ...]
    request_deadline_seconds: float
    hedge_delay_seconds: float
    model_cooldown_seconds: float

    def ordered_candidate_models(self) -> list[str]: ...

    def mark_model_cooldown(self, model_name: str, duration_seconds: float) -> None: ...


def is_non_retryable_client_error(exc: BaseException) -> bool:
    """Return True for non-retryable 4xx ClientErrors such as 401/403."""
    return isinstance(exc, ClientError) and getattr(exc, "code", None) not in (400, 404, 429)


async def _cancel_tasks[T](tasks: set[asyncio.Task[T]]) -> None:
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def _await_hedge_race[T](
    host: HedgedRunnerHost,
    *,
    primary_task: asyncio.Task[T],
    hedge_task: asyncio.Task[T],
    primary_model: str,
    hedge_model: str,
    deadline: float,
    attempts: list[ModelAttemptEntity],
    extract_t0: float,
) -> tuple[T | None, Exception | None]:
    active: set[asyncio.Task[T]] = {primary_task, hedge_task}
    last_error: Exception | None = None
    try:
        while active:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None, TimeoutError(
                    f"Extraction deadline ({host.request_deadline_seconds}s) exceeded."
                )
            finished, active = await asyncio.wait(
                active, timeout=remaining, return_when=asyncio.FIRST_COMPLETED
            )
            if not finished:
                return None, TimeoutError(
                    f"Extraction deadline ({host.request_deadline_seconds}s) exceeded."
                )

            winner = next(
                (t for t in finished if not t.cancelled() and t.exception() is None),
                None,
            )
            if winner is not None:
                result = winner.result()
                if active:
                    await _cancel_tasks(active)
                    loser_model = hedge_model if winner is primary_task else primary_model
                    attempts.append(
                        ModelAttemptEntity(
                            model=loser_model,
                            status="hedged_cancelled",
                            ms=int((time.perf_counter() - extract_t0) * 1000),
                        )
                    )
                return result, None

            for task in finished:
                exc = task.exception()
                if exc is not None and is_non_retryable_client_error(exc):
                    await _cancel_tasks(active)
                    raise exc
                if isinstance(exc, Exception):
                    last_error = exc
    finally:
        await _cancel_tasks(active)
    return None, last_error


async def _run_hedged_pair[T](
    host: HedgedRunnerHost,
    *,
    primary_model: str,
    hedge_model: str,
    run_model: Callable[[str], Awaitable[T]],
    deadline: float,
    attempts: list[ModelAttemptEntity],
    extract_t0: float,
) -> tuple[T | None, Exception | None, int]:
    primary_task = asyncio.create_task(run_model(primary_model))
    done, _ = await asyncio.wait({primary_task}, timeout=host.hedge_delay_seconds)
    if primary_task in done:
        exc = primary_task.exception()
        if exc is None:
            return primary_task.result(), None, 0
        if is_non_retryable_client_error(exc):
            raise exc
        if isinstance(exc, (ClientError, ServerError, TimeoutError, ValueError, httpx.HTTPError)):
            return None, exc, 1
        raise exc

    hedge_task = asyncio.create_task(run_model(hedge_model))
    winner, last_error = await _await_hedge_race(
        host,
        primary_task=primary_task,
        hedge_task=hedge_task,
        primary_model=primary_model,
        hedge_model=hedge_model,
        deadline=deadline,
        attempts=attempts,
        extract_t0=extract_t0,
    )
    if winner is not None:
        return winner, None, 0
    return None, last_error, 2


async def run_hedged_chain[T](
    host: HedgedRunnerHost,
    *,
    run_model: Callable[[str], Awaitable[T]],
    attempts: list[ModelAttemptEntity],
    extract_t0: float,
) -> T:
    """Run ordered candidate models with deadline, fail-fast 401/403, and hedging."""
    candidates = host.ordered_candidate_models()
    deadline = time.monotonic() + host.request_deadline_seconds
    last_error: Exception | None = None
    index = 0

    while index < len(candidates):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            last_error = TimeoutError(
                f"Extraction deadline ({host.request_deadline_seconds}s) exceeded."
            )
            break

        primary_model = candidates[index]
        if index + 1 < len(candidates) and remaining > host.hedge_delay_seconds:
            result, pair_err, step = await _run_hedged_pair(
                host,
                primary_model=primary_model,
                hedge_model=candidates[index + 1],
                run_model=run_model,
                deadline=deadline,
                attempts=attempts,
                extract_t0=extract_t0,
            )
            if result is not None:
                return result
            last_error = pair_err
            index += step
            continue

        try:
            return await asyncio.wait_for(run_model(primary_model), timeout=remaining)
        except TimeoutError as exc:
            last_error = TimeoutError(
                f"Extraction deadline ({host.request_deadline_seconds}s) exceeded."
            )
            host.mark_model_cooldown(primary_model, host.model_cooldown_seconds)
            if deadline - time.monotonic() <= 0:
                raise last_error from exc
        except (ClientError, ServerError, ValueError, httpx.HTTPError) as exc:
            if is_non_retryable_client_error(exc):
                raise
            last_error = exc
        index += 1

    if isinstance(last_error, TimeoutError):
        raise last_error
    raise RuntimeError(
        f"All Gemini models failed ({', '.join(host.model_chain)}). Last error: {last_error}"
    ) from last_error
