"""Currency rates gateway with read-through cache and layered fallbacks."""

import logging
import threading
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import httpx
from django.db import transaction

from apps.lots.integrations.currency.cache import CurrencyCache
from apps.lots.integrations.currency.client import CbrfClient, CbrfFetchError
from apps.lots.integrations.currency.domain import (
    JPY_RATE_SOURCE_TEMPLATE,
    BaseRates,
    CurrencyRatesResult,
    RatesOrigin,
    compute_commercial_jpy,
    parse_fallback_config,
)
from apps.lots.schemas import CurrencyRates
from config.settings.config import get_settings

logger = logging.getLogger(__name__)


class CurrencyRatesService:
    """Resolves a single rates set per calculation with provenance metadata.

    Resolution order: fresh cache -> live fetch (single updater under a short
    DB lease, others fall back immediately) -> last valid DB set no older
    than seven days -> configured fallback rates.
    """

    def __init__(
        self,
        *,
        client: CbrfClient,
        cache: CurrencyCache,
        fallback_config: BaseRates,
        spread: Decimal,
        ttl: timedelta,
    ) -> None:
        self._client = client
        self._cache = cache
        self._fallback_config = fallback_config
        self._spread = spread
        self._ttl = ttl
        self._lock_state = threading.local()

    def get_currency_rates(self) -> CurrencyRatesResult:
        return self._resolve(force=False)

    def refresh(self) -> CurrencyRatesResult:
        """Force an update, sharing the same lock and failure handling as normal reads."""
        return self._resolve(force=True)

    def _read_cached_result(self) -> CurrencyRatesResult | None:
        fresh = self._cache.read_fresh()
        if fresh is not None:
            rates, fetched_at = fresh
            return self._result(rates, RatesOrigin.CACHE, fetched_at, is_fallback=False)
        if self._cache.is_paused():
            return self._from_stale_or_config("source pause after a recent failure")
        return None

    def _resolve(self, *, force: bool) -> CurrencyRatesResult:
        if not force and (cached := self._read_cached_result()) is not None:
            return cached
        if not self._try_acquire_updater_lock():
            return self._from_stale_or_config("another process is updating rates")
        try:
            # A previous updater may have finished between the first read and acquiring the lease.
            if not force and (cached := self._read_cached_result()) is not None:
                return cached
            try:
                live, fetched_at = self._client.fetch_rates()
            except CbrfFetchError as exc:
                logger.warning("CBRF fetch failed: %s", exc)
                self._cache.mark_pause()
                return self._from_stale_or_config(f"source error: {exc}")
            with transaction.atomic():
                self._cache.write(live, fetched_at, ttl=self._ttl)
                self._cache.clear_pause()
            return self._result(live, RatesOrigin.LIVE, fetched_at, is_fallback=False)
        finally:
            self._release_updater_lock()

    def _from_stale_or_config(self, reason: str) -> CurrencyRatesResult:
        stale = self._cache.read_stale()
        if stale is not None:
            rates, fetched_at = stale
            logger.warning("Using stale CBRF rates of %s (%s)", rates.cbrf_date, reason)
            return self._result(
                rates, RatesOrigin.STALE, fetched_at, is_fallback=True, reason=reason
            )
        fallback = self._fallback_config
        rates = BaseRates(
            eur_rub=fallback.eur_rub,
            usd_rub=fallback.usd_rub,
            jpy_rub=fallback.jpy_rub,
            cbrf_date=fallback.cbrf_date,
        )
        logger.warning("Using configured fallback CBRF rates of %s (%s)", rates.cbrf_date, reason)
        return self._result(
            rates,
            RatesOrigin.CONFIG,
            datetime.now(UTC),
            is_fallback=True,
            reason=reason,
        )

    def _result(
        self,
        base: BaseRates,
        origin: RatesOrigin,
        fetched_at: datetime,
        *,
        is_fallback: bool,
        reason: str | None = None,
    ) -> CurrencyRatesResult:
        spread_pct = (self._spread * Decimal(100)).normalize()
        jpy_source = JPY_RATE_SOURCE_TEMPLATE.format(pct=spread_pct)
        commercial_jpy = float(compute_commercial_jpy(Decimal(str(base.jpy_rub)), self._spread))
        return CurrencyRatesResult(
            base=base,
            commercial_jpy_rub=commercial_jpy,
            jpy_rate_source=jpy_source,
            origin=origin,
            fetched_at=fetched_at,
            is_fallback=is_fallback,
            fallback_reason=reason,
        )

    def _try_acquire_updater_lock(self) -> bool:
        owner = uuid4().hex
        if self._cache.try_acquire_lock(owner):
            self._lock_state.owner = owner
            return True
        self._lock_state.owner = None
        return False

    def _release_updater_lock(self) -> None:
        owner = getattr(self._lock_state, "owner", None)
        self._lock_state.owner = None
        if owner is not None:
            self._cache.release_lock(owner)


def to_currency_rates_schema(result: CurrencyRatesResult) -> CurrencyRates:
    """Convert a gateway result to the existing public snapshot contract."""
    return CurrencyRates(
        jpy_rub_bank=result.commercial_jpy_rub,
        jpy_rate_source=result.jpy_rate_source,
        eur_rub_cbrf=result.eur_rub,
        usd_rub_cbrf=result.usd_rub,
        cbrf_date=result.cbrf_date,
    )


def to_customs_rates_input(result: CurrencyRatesResult) -> dict:
    """Serialize a gateway snapshot for BE-09 consumption."""
    return to_currency_rates_schema(result).model_dump()


def build_currency_service(
    *, transport: httpx.BaseTransport | None = None, cache: CurrencyCache | None = None
) -> CurrencyRatesService:
    """Assemble the gateway from settings, with explicit local demonstration reserves."""
    settings = get_settings()
    fallback = parse_fallback_config(settings.CBRF_FALLBACK_RATES)
    if fallback is None:
        fallback = BaseRates(95.0, 85.0, 0.5825, "01.01.2026")
    return CurrencyRatesService(
        client=CbrfClient(
            api_url=settings.CBRF_API_URL,
            timeout_sec=settings.CBRF_TIMEOUT_SEC,
            transport=transport,
        ),
        cache=cache if cache is not None else CurrencyCache(),
        fallback_config=fallback,
        spread=Decimal(str(settings.CBRF_JPY_SPREAD)),
        ttl=timedelta(hours=1),
    )
