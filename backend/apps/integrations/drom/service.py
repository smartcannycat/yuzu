"""Drom market evaluation facade orchestrating power lookup, cache, and regional cascade."""

import contextlib
import logging
from dataclasses import replace
from datetime import timedelta
from typing import Any

from django.conf import settings

from apps.integrations.drom.cache import fetch_with_drom_cache, write_drom_cache
from apps.integrations.drom.cascade import (
    DromCascadeExecutor,
    _same_slug,
    _SearchStep,
    build_step_url,
)
from apps.integrations.drom.client import DromHttpClient
from apps.integrations.drom.filtering import compute_engine_volume_bounds, is_manual_transmission
from apps.integrations.drom.power import DromPowerResolver
from apps.integrations.drom.schemas import (
    DromFetchError,
    DromMarketResult,
    DromPowerResult,
    DromSearchCriteria,
)
from apps.integrations.drom.slugs import DromSlugResolver, ResolvedDromSlug
from apps.integrations.shared.cache import bound_cache_key

logger = logging.getLogger(__name__)

_MARKET_CACHE_TTL = timedelta(hours=6)

__all__ = [
    "DromMarketService",
    "_SearchStep",
    "_build_market_cache_key",
]


class DromMarketService:
    """Orchestrates Drom analog search, read-through caching, and power_hp lookup."""

    def __init__(self, client: DromHttpClient | None = None) -> None:
        self._managed_client = client is None
        self._client = client or DromHttpClient(
            timeout_sec=float(getattr(settings, "SCRAPER_TIMEOUT_SEC", 10.0)),
            request_interval_sec=float(getattr(settings, "SCRAPER_REQUEST_INTERVAL_SEC", 1.2)),
            request_jitter_sec=float(getattr(settings, "SCRAPER_REQUEST_JITTER_SEC", 0.4)),
            proxy_ban_sec=float(getattr(settings, "SCRAPER_PROXY_BAN_SEC", 120)),
            proxy_urls=getattr(settings, "SCRAPER_PROXY_URLS", ()),
        )
        self._slug_resolver = DromSlugResolver(self._client)
        self._power_resolver = DromPowerResolver(self._client, self._slug_resolver)
        self._cascade = DromCascadeExecutor(self._client, self._slug_resolver)

    def evaluate(self, criteria: DromSearchCriteria) -> DromMarketResult:
        """Fetch Drom market analogs and engine power_hp for a parsed auction lot."""
        budget_sec = max(self._client._timeout_sec * 6.0, 45.0)
        budget_ctx = (
            self._client.budget(budget_sec)
            if hasattr(self._client, "budget")
            else contextlib.nullcontext()
        )
        with budget_ctx:
            if self._managed_client and hasattr(type(self._client), "__enter__"):
                with self._client:
                    return self._evaluate_with_client(criteria)
            return self._evaluate_with_client(criteria)

    def _evaluate_with_client(self, criteria: DromSearchCriteria) -> DromMarketResult:
        power = self._power_resolver.resolve(
            make=criteria.make,
            model=criteria.model,
            model_code=criteria.model_code,
            engine_cc=criteria.engine_cc,
            fuel_type=criteria.fuel_type,
            drive_type=criteria.drive_type,
            year=criteria.year,
            trim=criteria.trim,
        )

        initial_slug = self._slug_resolver.resolve(criteria.make, criteria.model)
        current_slug = initial_slug
        cache_key = _build_market_cache_key(criteria, initial_slug)

        def _fetch_live() -> DromMarketResult | None:
            nonlocal current_slug
            live_result, current_slug = self._cascade.run(criteria, current_slug)
            return live_result

        result, is_stale = fetch_with_drom_cache(
            cache_key,
            fetcher=_fetch_live,
            serialize=_serialize_market_result,
            deserialize=_deserialize_market_result,
            ttl=_MARKET_CACHE_TTL,
            fallback_to_stale_on_empty=True,
            on_error=lambda exc: logger.warning(
                "Drom live lookup failed for %s %s: %s", criteria.make, criteria.model, exc
            ),
        )
        if result is not None and not is_stale and not _same_slug(current_slug, initial_slug):
            resolved_key = _build_market_cache_key(criteria, current_slug)
            if resolved_key != cache_key:
                write_drom_cache(
                    resolved_key, _serialize_market_result(result), ttl=_MARKET_CACHE_TTL
                )
        if result is not None:
            if is_stale:
                result = _mark_stale_fallback(result)
            return _with_power(result, power)

        raise DromFetchError(
            f"Не удалось получить рыночные аналоги Drom для {criteria.make} {criteria.model}"
        )

    def _search_live_cascade(
        self,
        criteria: DromSearchCriteria,
        slug: ResolvedDromSlug,
    ) -> tuple[DromMarketResult | None, ResolvedDromSlug]:
        return self._cascade.run(criteria, slug)

    @staticmethod
    def _build_step_url(
        criteria: DromSearchCriteria,
        slug: ResolvedDromSlug,
        step: _SearchStep,
    ) -> str:
        return build_step_url(criteria, slug, step)


def _deserialize_market_result(payload: dict[str, Any]) -> DromMarketResult | None:
    try:
        market_price = int(payload["market_price_rf_rub"])
        analogs_count = int(payload["analogs_count"])
        if market_price < 0 or analogs_count < 0:
            return None
        price_min = payload.get("price_min_rub")
        price_max = payload.get("price_max_rub")
        return DromMarketResult(
            market_price_rf_rub=market_price,
            analogs_count=analogs_count,
            price_min_rub=int(price_min) if price_min is not None else None,
            price_max_rub=int(price_max) if price_max is not None else None,
            search_region_ru=str(payload["search_region_ru"]),
            excludes_under_order=bool(payload.get("excludes_under_order", True)),
            filtered_out_under_order_count=max(
                0, int(payload.get("filtered_out_under_order_count", 0))
            ),
            is_fallback=bool(payload.get("is_fallback", False)),
            fallback_reason_ru=payload.get("fallback_reason_ru"),
            drom_search_url=str(payload["drom_search_url"])[:500],
        )
    except (KeyError, TypeError, ValueError):
        return None


def _serialize_market_result(result: DromMarketResult) -> dict[str, Any]:
    return {
        "market_price_rf_rub": result.market_price_rf_rub,
        "analogs_count": result.analogs_count,
        "price_min_rub": result.price_min_rub,
        "price_max_rub": result.price_max_rub,
        "search_region_ru": result.search_region_ru,
        "excludes_under_order": result.excludes_under_order,
        "filtered_out_under_order_count": result.filtered_out_under_order_count,
        "is_fallback": result.is_fallback,
        "fallback_reason_ru": result.fallback_reason_ru,
        "drom_search_url": result.drom_search_url,
    }


def _build_market_cache_key(criteria: DromSearchCriteria, slug: ResolvedDromSlug) -> str:
    if criteria.engine_cc and criteria.engine_cc > 0:
        min_v, max_v = compute_engine_volume_bounds(criteria.engine_cc, delta=0.1)
        cc_bucket = f"{min_v:.1f}-{max_v:.1f}"
    else:
        cc_bucket = "any"
    trans_bucket = "mt" if is_manual_transmission(criteria.transmission) else "any"
    key = (
        f"drom:market:{slug.make_slug}:{slug.model_slug}:"
        f"y={criteria.year or 'any'}:cc={cc_bucket}:"
        f"drv={criteria.drive_type or 'any'}:fuel={criteria.fuel_type or 'any'}:"
        f"tr={trans_bucket}:ft={slug.frame_type_id or 'any'}"
    )
    return bound_cache_key(key, prefix="drom:market")


def _with_power(result: DromMarketResult, power: DromPowerResult) -> DromMarketResult:
    return replace(
        result,
        power_hp=power.power_hp,
        power_hp_source=power.power_hp_source,
        is_under_160_hp=power.is_under_160_hp,
    )


def _mark_stale_fallback(result: DromMarketResult) -> DromMarketResult:
    return replace(
        result,
        is_fallback=True,
        fallback_reason_ru=(
            result.fallback_reason_ru
            or "Drom.ru временно недоступен — показаны последние кэшированные данные"
        ),
    )
