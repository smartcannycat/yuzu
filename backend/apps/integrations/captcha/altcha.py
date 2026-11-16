"""ALTCHA proof-of-work solver (parallel worker search and key derivation)."""

from __future__ import annotations

import hashlib
import os
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

from apps.integrations.captcha.altcha_challenge import (
    _PBKDF2_ALGORITHMS,
    _SHA_ALGORITHMS,
    AltchaChallenge,
    AltchaError,
    AltchaSolution,
    AltchaSolveTimeoutError,
    AltchaUnsupportedAlgorithmError,
    build_altcha_payload,
)

try:  # pragma: no cover - exercised through the argon2id unit test
    from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
except ImportError:  # pragma: no cover - optional at import time
    Argon2id = None  # type: ignore[assignment,misc]

_DEFAULT_WORKERS = 8
_ARGON2_MAX_WORKERS = 4
_MAX_WORKERS = 16
_DEFAULT_V2_MAXNUMBER = 10_000_000

__all__ = [
    "AltchaChallenge",
    "AltchaError",
    "AltchaSolution",
    "AltchaSolveTimeoutError",
    "AltchaUnsupportedAlgorithmError",
    "build_altcha_payload",
    "solve_altcha",
    "solve_altcha_payload",
]


def _wait_for_worker_solution(
    futures: list[Future[AltchaSolution | None]],
    stop: threading.Event,
    deadline: float | None,
) -> AltchaSolution | None:
    pending = futures
    while pending:
        timeout: float | None = None
        if deadline is not None:
            timeout = deadline - time.monotonic()
            if timeout <= 0:
                stop.set()
                return None
        done, _ = wait(pending, timeout=timeout, return_when=FIRST_COMPLETED)
        if not done:
            stop.set()
            return None
        pending = [future for future in pending if not future.done()]
        for future in done:
            candidate = future.result()
            if candidate is not None:
                stop.set()
                return candidate
    return None


def solve_altcha(
    challenge: AltchaChallenge,
    *,
    deadline: float | None = None,
    max_workers: int | None = None,
) -> AltchaSolution:
    """Find a counter whose derived key satisfies the challenge."""
    started = time.monotonic()
    workers = _resolve_workers(max_workers, challenge=challenge)
    max_counter = (
        challenge.max_number
        if challenge.max_number is not None
        else (_DEFAULT_V2_MAXNUMBER if deadline is None else None)
    )
    stop = threading.Event()

    def attempt(offset: int, step: int) -> AltchaSolution | None:
        counter = offset
        while not stop.is_set():
            if deadline is not None and time.monotonic() >= deadline:
                return None
            if max_counter is not None and counter > max_counter:
                return None
            derived = _derive_key(challenge, counter)
            if _matches(challenge, derived):
                stop.set()
                elapsed = int((time.monotonic() - started) * 1000)
                return AltchaSolution(counter, derived.hex(), elapsed)
            counter += step
        return None

    result: AltchaSolution | None = None
    executor = ThreadPoolExecutor(max_workers=workers)
    try:
        futures = [executor.submit(attempt, offset, workers) for offset in range(workers)]
        result = _wait_for_worker_solution(futures, stop, deadline)
    finally:
        stop.set()
        executor.shutdown(wait=False, cancel_futures=True)

    if result is None:
        if deadline is not None and time.monotonic() >= deadline:
            raise AltchaSolveTimeoutError("ALTCHA solution deadline reached")
        raise AltchaSolveTimeoutError("ALTCHA solution was not found in the search range")
    return result


def solve_altcha_payload(
    challenge: AltchaChallenge,
    *,
    deadline: float | None = None,
    max_workers: int | None = None,
) -> str:
    """Solve ``challenge`` and return the value for the ALTCHA form field."""
    return build_altcha_payload(
        challenge,
        solve_altcha(challenge, deadline=deadline, max_workers=max_workers),
    )


def _resolve_workers(
    max_workers: int | None,
    *,
    challenge: AltchaChallenge | None = None,
) -> int:
    cpu_count = os.cpu_count() or 4
    requested = _DEFAULT_WORKERS if max_workers is None else max_workers
    if requested <= 0:
        requested = cpu_count
    capped = max(1, min(requested, cpu_count, _MAX_WORKERS))
    if (
        challenge is not None
        and challenge.algorithm == "argon2id"
        and challenge.memory_cost >= 8192
    ):
        return min(capped, _ARGON2_MAX_WORKERS)
    return capped


def _derive_key(challenge: AltchaChallenge, counter: int) -> bytes:
    if challenge.version == 1:
        password = challenge.nonce + str(counter).encode()
    else:
        password = challenge.nonce + counter.to_bytes(4, "big", signed=False)
    if challenge.algorithm == "argon2id":
        if Argon2id is None:
            raise AltchaUnsupportedAlgorithmError(
                "argon2id ALTCHA challenges require the cryptography package"
            )
        return Argon2id(
            salt=challenge.salt,
            length=challenge.key_length,
            iterations=challenge.cost,
            lanes=challenge.parallelism,
            memory_cost=challenge.memory_cost,
        ).derive(password)
    if challenge.algorithm in _PBKDF2_ALGORITHMS:
        return hashlib.pbkdf2_hmac(
            _PBKDF2_ALGORITHMS[challenge.algorithm],
            password,
            challenge.salt,
            challenge.cost,
            dklen=challenge.key_length,
        )
    digest_name = _SHA_ALGORITHMS[challenge.algorithm]
    digest = hashlib.new(digest_name, challenge.salt + password).digest()
    digest = digest[: challenge.key_length]
    for _ in range(challenge.cost - 1):
        digest = hashlib.new(digest_name, digest).digest()[: challenge.key_length]
    return digest


def _matches(challenge: AltchaChallenge, derived: bytes) -> bool:
    if challenge.key_prefix_hex and len(challenge.key_prefix_hex) % 2:
        return derived.hex().startswith(challenge.key_prefix_hex)
    return derived.startswith(challenge.key_prefix)
