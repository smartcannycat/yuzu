"""ALTCHA v1/v2 challenge parsing, error types, and payload serialization."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

_MAX_MAXNUMBER = 50_000_000
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
