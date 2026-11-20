"""Per-batch distributed Redis leases and resource-closing helpers for the pipeline."""

from __future__ import annotations

import contextlib
import logging
import threading
import uuid
from typing import TYPE_CHECKING

from redis.exceptions import RedisError

from apps.core import redis_utils

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)

BATCH_LOCK_TTL_SEC = 180

_RENEW_LEASE_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
end
return 0
"""

_RELEASE_LEASE_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""

_LEASE_LOCK = threading.Lock()
_ACTIVE_BATCH_LEASES: dict[str, str] = {}


def batch_lock_key(batch_id: uuid.UUID | str) -> str:
    """Return the canonical Redis key guarding exclusive processing for ``batch_id``."""
    return f"yuzu:batch:lock:{batch_id}"


def acquire_batch_lease(
    batch_id: uuid.UUID | str,
    *,
    ttl_sec: int = BATCH_LOCK_TTL_SEC,
) -> bool:
    """Acquire an exclusive per-batch lease (Redis NX+EX when configured, plus local guard)."""
    key_id = str(batch_id)
    with _LEASE_LOCK:
        if key_id in _ACTIVE_BATCH_LEASES:
            return False

    token = uuid.uuid4().hex
    client = redis_utils.get_redis_client()
    redis_key = batch_lock_key(key_id)
    if client is not None:
        try:
            acquired = bool(client.set(redis_key, token, nx=True, ex=ttl_sec))
        except (RedisError, OSError) as exc:
            logger.warning("Could not acquire batch lease %s: %s", redis_key, exc)
            return False
        if not acquired:
            return False

    with _LEASE_LOCK:
        if key_id in _ACTIVE_BATCH_LEASES:
            if client is not None:
                try:
                    client.eval(_RELEASE_LEASE_LUA, 1, redis_key, token)
                except (RedisError, OSError):
                    logger.warning("Failed to release duplicate local batch lease %s", redis_key)
            return False
        _ACTIVE_BATCH_LEASES[key_id] = token
    return True


def renew_batch_lease(
    batch_id: uuid.UUID | str,
    *,
    ttl_sec: int = BATCH_LOCK_TTL_SEC,
) -> bool:
    """Extend the active Redis lease for ``batch_id`` if still owned by this worker."""
    key_id = str(batch_id)
    with _LEASE_LOCK:
        token = _ACTIVE_BATCH_LEASES.get(key_id)
    if token is None:
        return False

    client = redis_utils.get_redis_client()
    if client is None:
        return True
    redis_key = batch_lock_key(key_id)
    try:
        return bool(client.eval(_RENEW_LEASE_LUA, 1, redis_key, token, str(ttl_sec)))
    except (RedisError, OSError) as exc:
        logger.warning("Failed to renew batch lease %s: %s", redis_key, exc)
        return False


def release_batch_lease(batch_id: uuid.UUID | str) -> None:
    """Release the per-batch Redis lease only if our owner token still matches."""
    key_id = str(batch_id)
    with _LEASE_LOCK:
        token = _ACTIVE_BATCH_LEASES.pop(key_id, None)
    if token is None:
        return

    client = redis_utils.get_redis_client()
    if client is None:
        return
    redis_key = batch_lock_key(key_id)
    try:
        client.eval(_RELEASE_LEASE_LUA, 1, redis_key, token)
    except (RedisError, OSError) as exc:
        logger.warning("Failed to release batch lease %s: %s", redis_key, exc)


def is_batch_lease_held(batch_id: uuid.UUID | str) -> bool:
    """Return True if ``batch_id`` currently has an active local or Redis lease."""
    key_id = str(batch_id)
    with _LEASE_LOCK:
        if key_id in _ACTIVE_BATCH_LEASES:
            return True

    client = redis_utils.get_redis_client()
    if client is None:
        return False
    redis_key = batch_lock_key(key_id)
    try:
        return bool(client.exists(redis_key))
    except (RedisError, OSError) as exc:
        logger.warning("Could not inspect batch lease %s: %s", redis_key, exc)
        return True


@contextlib.contextmanager
def managed_closing[T](resource: T) -> Iterator[T]:
    """Use ``contextlib.closing`` when ``resource`` defines ``close()``."""
    if callable(getattr(resource, "close", None)):
        with contextlib.closing(resource):  # type: ignore[type-var]
            yield resource
    else:
        yield resource
