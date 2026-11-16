"""ALTCHA proof-of-work challenge solving shared by anti-bot protected scrapers.

ALTCHA has two on-the-wire formats:

* legacy (v1): a flat JSON object with ``challenge`` (a full hash), ``salt`` and
  ``maxnumber``; the client searches the number whose hash equals ``challenge``.
* modern (v2): a ``parameters`` object with ``nonce``, ``salt``, ``keyPrefix``
  and an algorithm; the client searches the counter whose derived key starts
  with ``keyPrefix``.

Both variants are implemented here so scrapers only need to know how to fetch
the challenge JSON and where to submit the resulting payload.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import time
from collections.abc import Mapping
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any

try:  # pragma: no cover - exercised through the argon2id unit test
    from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
except ImportError:  # pragma: no cover - optional at import time
    Argon2id = None  # type: ignore[assignment,misc]

_DEFAULT_WORKERS = 8
_ARGON2_MAX_WORKERS = 4
_MAX_WORKERS = 16
_MAX_MAXNUMBER = 50_000_000
_DEFAULT_V2_MAXNUMBER = 10_000_000
_MAX_ARGON2_MEMORY_COST = 131_072
_MAX_ARGON2_PARALLELISM = 4
_MAX_ARGON2_COST = 100
_MAX_PBKDF2_COST = 200_000
_MAX_SHA_COST = 1_000_000
_SHA_ALGORITHMS = {
    "SHA-256": "sha256",
    "SHA-384": "sha384",
    "SHA-512": "sha512",
}
_PBKDF2_ALGORITHMS = {
    "PBKDF2/SHA-256": "sha256",
    "PBKDF2/SHA-384": "sha384",
    "PBKDF2/SHA-512": "sha512",
}
_DIGEST_LENGTHS = {"SHA-256": 32, "SHA-384": 48, "SHA-512": 64}


class AltchaError(RuntimeError):
    """Base error for malformed, unsupported or timed-out ALTCHA challenges."""


class AltchaUnsupportedAlgorithmError(AltchaError):
    """The challenge uses an algorithm this backend cannot derive."""


class AltchaSolveTimeoutError(AltchaError):
    """No solution was found before the caller's deadline."""


@dataclass(frozen=True)
class AltchaChallenge:
    """Normalized representation of an ALTCHA challenge."""

    algorithm: str
    key_prefix: bytes
    key_prefix_hex: str
    nonce: bytes
    salt: bytes
    cost: int = 1
    key_length: int = 32
    memory_cost: int = 16_384
    parallelism: int = 1
    max_number: int | None = None
    signature: str = ""
    original_salt: str = ""
    parameters: dict[str, Any] | None = None
    version: int = 2

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> AltchaChallenge:
        """Build a challenge from either the v1 or v2 JSON response."""
        if not isinstance(payload, Mapping):
            raise AltchaError("ALTCHA challenge must be a JSON object")
        parameters = payload.get("parameters")
        if isinstance(parameters, Mapping):
            return cls._from_v2(payload, parameters)
        return cls._from_v1(payload)

    @classmethod
    def _from_v1(cls, payload: Mapping[str, Any]) -> AltchaChallenge:
        algorithm = str(payload.get("algorithm") or "")
        if algorithm not in _SHA_ALGORITHMS:
            raise AltchaUnsupportedAlgorithmError(f"Unsupported ALTCHA algorithm: {algorithm}")
        challenge = str(payload.get("challenge") or "")
        salt = str(payload.get("salt") or "")
        try:
            key_prefix = bytes.fromhex(challenge)
        except ValueError as exc:
            raise AltchaError("ALTCHA v1 challenge is not valid hex") from exc
        if not key_prefix:
            raise AltchaError("ALTCHA v1 challenge is empty")
        try:
            max_number = int(payload.get("maxnumber", 1_000_000))
        except (TypeError, ValueError) as exc:
            raise AltchaError("ALTCHA v1 maxnumber is not an integer") from exc
        return cls(
            algorithm=algorithm,
            key_prefix=key_prefix,
            key_prefix_hex=challenge.lower(),
            nonce=salt.encode(),
            salt=b"",
            cost=1,
            key_length=_DIGEST_LENGTHS[algorithm],
            max_number=max(0, min(max_number, _MAX_MAXNUMBER)),
            signature=str(payload.get("signature") or ""),
            original_salt=salt,
            version=1,
        )

    @classmethod
    def _from_v2(cls, payload: Mapping[str, Any], parameters: Mapping[str, Any]) -> AltchaChallenge:
        algorithm = str(parameters.get("algorithm") or "")
        if (
            algorithm not in _SHA_ALGORITHMS
            and algorithm not in _PBKDF2_ALGORITHMS
            and algorithm != "argon2id"
        ):
            raise AltchaUnsupportedAlgorithmError(f"Unsupported ALTCHA algorithm: {algorithm}")
        prefix_hex = str(parameters.get("keyPrefix") or "")
        if not prefix_hex:
            raise AltchaError("ALTCHA v2 keyPrefix is empty")
        if any(ch not in "0123456789abcdefABCDEF" for ch in prefix_hex):
            raise AltchaError("ALTCHA v2 keyPrefix is not valid hex")
        try:
            nonce = bytes.fromhex(str(parameters.get("nonce") or ""))
            salt = bytes.fromhex(str(parameters.get("salt") or ""))
        except ValueError as exc:
            raise AltchaError("ALTCHA v2 nonce/salt are not valid hex") from exc
        if not nonce:
            raise AltchaError("ALTCHA v2 nonce is empty")
        key_length = _clamp_int(parameters.get("keyLength", 32), 1, 128, 32)
        if algorithm == "argon2id":
            cost = _clamp_int(parameters.get("cost", 1), 1, _MAX_ARGON2_COST, 1)
            memory_cost = _clamp_int(
                parameters.get("memoryCost", 16_384), 8, _MAX_ARGON2_MEMORY_COST, 16_384
            )
            parallelism = _clamp_int(
                parameters.get("parallelism", 1), 1, _MAX_ARGON2_PARALLELISM, 1
            )
        elif algorithm in _PBKDF2_ALGORITHMS:
            cost = _clamp_int(parameters.get("cost", 1), 1, _MAX_PBKDF2_COST, 1)
            memory_cost = 16_384
            parallelism = 1
        else:
            cost = _clamp_int(parameters.get("cost", 1), 1, _MAX_SHA_COST, 1)
            memory_cost = 16_384
            parallelism = 1
        return cls(
            algorithm=algorithm,
            key_prefix=_hex_prefix(prefix_hex),
            key_prefix_hex=prefix_hex.lower(),
            nonce=nonce,
            salt=salt,
            cost=cost,
            key_length=key_length,
            memory_cost=memory_cost,
            parallelism=parallelism,
            signature=str(payload.get("signature") or ""),
            parameters=dict(parameters),
            version=2,
        )


@dataclass(frozen=True)
class AltchaSolution:
    """A proof-of-work solution, ready to be encoded into an ALTCHA payload."""

    counter: int
    derived_key: str = ""
    elapsed_ms: int = 0


def _clamp_int(value: Any, minimum: int, maximum: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


def _hex_prefix(value: str) -> bytes:
    if len(value) % 2:
        return b""
    try:
        return bytes.fromhex(value)
    except ValueError:
        return b""


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
        while futures and result is None:
            timeout: float | None = None
            if deadline is not None:
                timeout = deadline - time.monotonic()
                if timeout <= 0:
                    stop.set()
                    break
            done, _ = wait(futures, timeout=timeout, return_when=FIRST_COMPLETED)
            if not done:
                stop.set()
                break
            futures = [future for future in futures if not future.done()]
            for future in done:
                candidate = future.result()
                if candidate is not None:
                    result = candidate
                    stop.set()
                    break
    finally:
        stop.set()
        executor.shutdown(wait=False, cancel_futures=True)

    if result is None:
        if deadline is not None and time.monotonic() >= deadline:
            raise AltchaSolveTimeoutError("ALTCHA solution deadline reached")
        raise AltchaSolveTimeoutError("ALTCHA solution was not found in the search range")
    return result


def build_altcha_payload(challenge: AltchaChallenge, solution: AltchaSolution) -> str:
    """Encode a solved challenge as the base64 payload expected by ALTCHA widgets."""
    if challenge.version == 1:
        body: dict[str, Any] = {
            "algorithm": challenge.algorithm,
            "challenge": challenge.key_prefix_hex,
            "number": str(solution.counter),
            "salt": challenge.original_salt,
            "signature": challenge.signature,
            "took": solution.elapsed_ms,
        }
    else:
        body = {
            "challenge": {
                "parameters": challenge.parameters or {},
                "signature": challenge.signature,
            },
            "solution": {
                "counter": solution.counter,
                "derivedKey": solution.derived_key,
                "time": solution.elapsed_ms,
            },
        }
    encoded = json.dumps(body, separators=(",", ":"), ensure_ascii=True).encode()
    return base64.b64encode(encoded).decode("ascii")


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
