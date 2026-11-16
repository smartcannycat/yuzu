"""Drom-specific read-through ExternalCache facade backed by shared cache helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apps.core.enums import ExternalCacheSource
from apps.integrations.drom.schemas import DromFetchError
from apps.integrations.shared.cache import (
    fetch_with_external_cache,
    read_external_cache,
    upsert_external_cache,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import timedelta


def read_drom_cache(key: str, *, allow_stale: bool = False) -> dict[str, Any] | None:
    """Read cached JSON payload from ExternalCache, optionally allowing expired entries."""
    entry = read_external_cache(key, allow_stale=allow_stale)
    if entry is None:
        return None
    return entry.payload if isinstance(entry.payload, dict) else None


def write_drom_cache(key: str, payload: dict[str, Any], *, ttl: timedelta) -> None:
    """Upsert a JSON payload into ExternalCache safely under concurrent threads."""
    upsert_external_cache(key, source=ExternalCacheSource.DROM, payload=payload, ttl=ttl)


def fetch_with_drom_cache[T](
    key: str,
    *,
    fetcher: Callable[[], T | None],
    serialize: Callable[[T], dict[str, Any]],
    deserialize: Callable[[dict[str, Any]], T | None],
    ttl: timedelta,
    is_cacheable: Callable[[T], bool] | None = None,
    fallback_to_stale_on_empty: bool = True,
    on_error: Callable[[DromFetchError], None] | None = None,
    reraise: tuple[type[Exception], ...] = (),
) -> tuple[T | None, bool]:
    """Read-through Drom cache helper with stale fallback on fetch errors or empty results."""
    return fetch_with_external_cache(
        key,
        source=ExternalCacheSource.DROM,
        fetcher=fetcher,
        serialize=serialize,
        deserialize=deserialize,
        ttl=ttl,
        fetch_errors=(DromFetchError,),
        is_cacheable=is_cacheable,
        fallback_to_stale_on_empty=fallback_to_stale_on_empty,
        on_error=on_error,  # type: ignore[arg-type]
        reraise=reraise,
        read_payload=lambda k, allow_stale: read_drom_cache(k, allow_stale=allow_stale),
        write_payload=lambda k, payload, entry_ttl: write_drom_cache(k, payload, ttl=entry_ttl),
    )
