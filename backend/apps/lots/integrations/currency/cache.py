"""Read-through cache for CBRF currency rates on top of ExternalCache."""

from datetime import datetime, timedelta
from typing import Any

from django.utils import timezone

from apps.core.enums import ExternalCacheSource
from apps.core.models import ExternalCache
from apps.lots.integrations.currency.domain import BaseRates, parse_fallback_config

CACHE_KEY = "cbrf:currency_rates:v1"
STALE_MAX_AGE = timedelta(days=7)

# Separate marker written after a failed source request so a broken upstream
# does not turn every calculation into a live HTTP call.
PAUSE_KEY = "cbrf:currency_rates:pause:v1"
PAUSE_TTL = timedelta(seconds=60)


class CurrencyCache:
    """PostgreSQL-backed cache of the last valid CBRF rates set.

    The payload stores normalized base rates as decimal strings to avoid
    float round-trip drift, plus the source date and the fetch timestamp.
    """

    def read_fresh(self) -> tuple[BaseRates, datetime] | None:
        entry = ExternalCache.objects.filter(key=CACHE_KEY).first()
        if entry is None or entry.expires_at <= timezone.now():
            return None
        return self._deserialize_entry(entry)

    def read_stale(self) -> tuple[BaseRates, datetime] | None:
        """Read the last valid set regardless of TTL, bounded by the stale age."""
        entry = ExternalCache.objects.filter(key=CACHE_KEY).first()
        if entry is None:
            return None
        parsed = self._deserialize_entry(entry)
        if parsed is None or timezone.now() - parsed[1] > STALE_MAX_AGE:
            return None
        return parsed

    def write(self, rates: BaseRates, fetched_at: datetime, *, ttl: timedelta) -> None:
        payload = self._serialize(rates, fetched_at)
        defaults = {
            "source": ExternalCacheSource.CBRF,
            "payload": payload,
            "expires_at": fetched_at + ttl,
        }
        ExternalCache.objects.update_or_create(key=CACHE_KEY, defaults=defaults)

    def is_paused(self, *, now: datetime | None = None) -> bool:
        entry = ExternalCache.objects.filter(key=PAUSE_KEY).first()
        if entry is None:
            return False
        moment = now or timezone.now()
        return entry.expires_at > moment

    def mark_pause(self, *, now: datetime | None = None) -> None:
        moment = now or timezone.now()
        ExternalCache.objects.update_or_create(
            key=PAUSE_KEY,
            defaults={
                "source": ExternalCacheSource.CBRF,
                "payload": {"reason": "source_error"},
                "expires_at": moment + PAUSE_TTL,
            },
        )

    def clear_pause(self) -> None:
        ExternalCache.objects.filter(key=PAUSE_KEY).delete()

    def _deserialize_entry(self, entry: ExternalCache) -> tuple[BaseRates, datetime] | None:
        parsed = self._deserialize(entry.payload)
        if parsed is None:
            return None
        rates, fetched_at = parsed
        return rates, fetched_at

    @staticmethod
    def _serialize(rates: BaseRates, fetched_at: datetime) -> dict[str, Any]:
        return {
            "eur_rub": str(rates.eur_rub),
            "usd_rub": str(rates.usd_rub),
            "jpy_rub": str(rates.jpy_rub),
            "cbrf_date": rates.cbrf_date,
            "fetched_at": fetched_at.isoformat(),
        }

    @staticmethod
    def _deserialize(payload: Any) -> tuple[BaseRates, datetime] | None:
        if not isinstance(payload, dict):
            return None
        try:
            rates = parse_fallback_config(payload)
            fetched_at = datetime.fromisoformat(str(payload["fetched_at"]))
            if timezone.is_naive(fetched_at) or fetched_at > timezone.now():
                return None
        except (KeyError, TypeError, ValueError):
            return None
        return (rates, fetched_at) if rates is not None else None
