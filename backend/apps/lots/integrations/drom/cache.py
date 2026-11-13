from datetime import timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.enums import ExternalCacheSource
from apps.core.models import ExternalCache


def read_drom_cache(key: str, *, allow_stale: bool = False) -> dict[str, Any] | None:
    """Read cached JSON payload from ExternalCache, optionally allowing expired entries."""
    entry = ExternalCache.objects.filter(key=key).first()
    if entry is None:
        return None
    if not allow_stale and entry.is_expired:
        return None
    return entry.payload if isinstance(entry.payload, dict) else None


def write_drom_cache(key: str, payload: dict[str, Any], *, ttl: timedelta) -> None:
    """Upsert a JSON payload into ExternalCache safely under concurrent threads."""
    expires_at = timezone.now() + ttl
    defaults = {
        "source": ExternalCacheSource.DROM,
        "payload": payload,
        "expires_at": expires_at,
    }
    try:
        with transaction.atomic():
            ExternalCache.objects.update_or_create(key=key, defaults=defaults)
    except IntegrityError:
        ExternalCache.objects.filter(key=key).update(**defaults, updated_at=timezone.now())
