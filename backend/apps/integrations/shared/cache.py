"""Shared concurrency-safe ExternalCache upsert and read-through helpers."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from django.db import IntegrityError, transaction
from django.utils import timezone

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime, timedelta

    from apps.core.enums import ExternalCacheSource
    from apps.core.models import ExternalCache


def bound_cache_key(key: str, *, prefix: str = "", max_length: int = 450) -> str:
    """Keep cache keys within ExternalCache.key limits via collision-safe SHA-256."""
    if len(key) <= max_length:
        return key
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    head = f"{prefix}:hash:" if prefix else "hash:"
    return f"{head}{digest}"[:512]


def read_external_cache(
    key: str,
    *,
    source: ExternalCacheSource | None = None,
    allow_stale: bool = False,
) -> ExternalCache | None:
    """Read an ExternalCache entry, or None when missing/expired (unless stale allowed)."""
    from apps.core.models import ExternalCache

    qs = ExternalCache.objects.filter(key=key)
    if source is not None:
        qs = qs.filter(source=source)
    entry = qs.first()
    if entry is None:
        return None
    if not allow_stale and entry.is_expired:
        return None
    return entry


def upsert_external_cache(
    key: str,
    *,
    source: ExternalCacheSource,
    payload: dict[str, Any],
    ttl: timedelta,
    now: datetime | None = None,
) -> None:
    """Atomically upsert an ExternalCache row, surviving concurrent inserts cleanly."""
    from apps.core.models import ExternalCache

    moment = now or timezone.now()
    defaults = {
        "source": source,
        "payload": payload,
        "expires_at": moment + ttl,
    }
    try:
        with transaction.atomic():
            ExternalCache.objects.update_or_create(key=key, defaults=defaults)
    except IntegrityError:
        ExternalCache.objects.filter(key=key).update(**defaults, updated_at=moment)


def _make_default_reader(
    source: ExternalCacheSource,
) -> Callable[[str, bool], dict[str, Any] | None]:
    def _read(cache_key: str, allow_stale: bool) -> dict[str, Any] | None:
        entry = read_external_cache(cache_key, source=source, allow_stale=allow_stale)
        if entry is None:
            return None
        return entry.payload if isinstance(entry.payload, dict) else None

    return _read


def _make_default_writer(
    source: ExternalCacheSource,
) -> Callable[[str, dict[str, Any], timedelta], None]:
    def _write(cache_key: str, payload: dict[str, Any], entry_ttl: timedelta) -> None:
        upsert_external_cache(cache_key, source=source, payload=payload, ttl=entry_ttl)

    return _write


def _read_deserialized[T](
    key: str,
    *,
    allow_stale: bool,
    reader: Callable[[str, bool], dict[str, Any] | None],
    deserialize: Callable[[dict[str, Any]], T | None],
) -> T | None:
    payload = reader(key, allow_stale)
    if payload is None:
        return None
    return deserialize(payload)


def fetch_with_external_cache[T](
    key: str,
    *,
    source: ExternalCacheSource,
    fetcher: Callable[[], T | None],
    serialize: Callable[[T], dict[str, Any]],
    deserialize: Callable[[dict[str, Any]], T | None],
    ttl: timedelta,
    fetch_errors: tuple[type[Exception], ...] = (),
    is_cacheable: Callable[[T], bool] | None = None,
    fallback_to_stale_on_empty: bool = True,
    on_error: Callable[[Exception], None] | None = None,
    reraise: tuple[type[Exception], ...] = (),
    read_payload: Callable[[str, bool], dict[str, Any] | None] | None = None,
    write_payload: Callable[[str, dict[str, Any], timedelta], None] | None = None,
) -> tuple[T | None, bool]:
    """Generic read-through cache over ExternalCache with stale fallback."""
    reader = read_payload or _make_default_reader(source)
    writer = write_payload or _make_default_writer(source)

    fresh_value = _read_deserialized(key, allow_stale=False, reader=reader, deserialize=deserialize)
    if fresh_value is not None:
        return fresh_value, False

    fetch_failed = False
    live_value: T | None = None
    try:
        live_value = fetcher()
    except fetch_errors as exc:
        if reraise and isinstance(exc, reraise):
            raise
        fetch_failed = True
        if on_error is not None:
            on_error(exc)

    if live_value is not None and (is_cacheable is None or is_cacheable(live_value)):
        writer(key, serialize(live_value), ttl)
        return live_value, False

    if fetch_failed or fallback_to_stale_on_empty:
        stale_value = _read_deserialized(
            key, allow_stale=True, reader=reader, deserialize=deserialize
        )
        if stale_value is not None:
            return stale_value, True

    return live_value, False
