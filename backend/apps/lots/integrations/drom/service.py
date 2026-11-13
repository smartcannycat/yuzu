import hashlib
import logging
from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Any

from django.conf import settings

from apps.lots.integrations.drom.cache import fetch_with_drom_cache
from apps.lots.integrations.drom.client import DromHttpClient
from apps.lots.integrations.drom.filtering import (
    FilteredMarketStats,
    build_drom_search_url,
    compute_engine_volume_bounds,
    filter_and_aggregate,
    is_manual_transmission,
)
from apps.lots.integrations.drom.parser import parse_listings
from apps.lots.integrations.drom.power import DromPowerResolver
from apps.lots.integrations.drom.schemas import (
    DromBlockedError,
    DromFetchError,
    DromMarketResult,
    DromNotFoundError,
    DromPowerResult,
    DromSearchCriteria,
)
from apps.lots.integrations.drom.slugs import DromSlugResolver, ResolvedDromSlug

logger = logging.getLogger(__name__)

_MARKET_CACHE_TTL = timedelta(hours=6)
_MIN_ANALOGS_THRESHOLD = 3


@dataclass(frozen=True, slots=True)
class _SearchStep:
    region_scope: str
    region_label_ru: str
    year_tolerance: int
    relax_specs: bool
    is_fallback: bool
    fallback_reason_ru: str | None


_SEARCH_CASCADE: tuple[_SearchStep, ...] = (
    _SearchStep(
        region_scope="dfo",
        region_label_ru="ДФО / Владивосток",
        year_tolerance=0,
        relax_specs=False,
        is_fallback=False,
        fallback_reason_ru=None,
    ),
    _SearchStep(
        region_scope="dfo",
        region_label_ru="ДФО / Владивосток",
        year_tolerance=1,
        relax_specs=True,
        is_fallback=True,
        fallback_reason_ru=(
            "Мало точных аналогов в наличии в ДФО — выборка расширена по годам (±1 год)"
        ),
    ),
    _SearchStep(
        region_scope="rf",
        region_label_ru="Вся РФ",
        year_tolerance=2,
        relax_specs=True,
        is_fallback=True,
        fallback_reason_ru=(
            "Мало точных аналогов в ДФО — выборка расширена на всю РФ (без пробега по РФ, ±2 года)"
        ),
    ),
)


class DromMarketService:
    """Orchestrates Drom analog search, Read-Through caching, and power_hp lookup."""

    def __init__(self, client: DromHttpClient | None = None) -> None:
        self._client = client or DromHttpClient(
            timeout_sec=float(getattr(settings, "HTTP_CLIENT_TIMEOUT_SEC", 10.0))
        )
        self._slug_resolver = DromSlugResolver(self._client)
        self._power_resolver = DromPowerResolver(self._client, self._slug_resolver)

    def evaluate(self, criteria: DromSearchCriteria) -> DromMarketResult:
        """Fetch Drom market analogs and engine power_hp for a parsed auction lot."""
        power = self._power_resolver.resolve(
            make=criteria.make,
            model=criteria.model,
            model_code=criteria.model_code,
            engine_cc=criteria.engine_cc,
            fuel_type=criteria.fuel_type,
            drive_type=criteria.drive_type,
            year=criteria.year,
        )

        current_slug = self._slug_resolver.resolve(criteria.make, criteria.model)
        cache_key = _build_market_cache_key(criteria, current_slug)

        def _fetch_live() -> DromMarketResult | None:
            nonlocal current_slug
            live_result, current_slug = self._search_live_cascade(criteria, current_slug)
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
        resolved_slug: ResolvedDromSlug,
    ) -> tuple[DromMarketResult | None, ResolvedDromSlug]:
        best_partial: DromMarketResult | None = None
        current_slug = resolved_slug
        last_error: DromFetchError | None = None

        for step in _SEARCH_CASCADE:
            try:
                stats, used_url, current_slug = self._fetch_step(criteria, current_slug, step)
            except DromBlockedError:
                if best_partial is not None:
                    return best_partial, current_slug
                raise
            except DromFetchError as exc:
                last_error = exc
                continue

            if stats is None:
                continue

            candidate = DromMarketResult(
                market_price_rf_rub=stats.market_price_rf_rub,
                analogs_count=stats.analogs_count,
                price_min_rub=stats.price_min_rub,
                price_max_rub=stats.price_max_rub,
                search_region_ru=step.region_label_ru,
                excludes_under_order=True,
                filtered_out_under_order_count=stats.filtered_out_under_order_count,
                is_fallback=step.is_fallback,
                fallback_reason_ru=step.fallback_reason_ru,
                drom_search_url=used_url,
            )
            if stats.analogs_count >= _MIN_ANALOGS_THRESHOLD:
                return candidate, current_slug
            if best_partial is None or candidate.analogs_count > best_partial.analogs_count:
                best_partial = candidate

        if best_partial is None and last_error is not None:
            raise last_error
        return best_partial, current_slug

    def _fetch_step_html(
        self,
        criteria: DromSearchCriteria,
        slug: ResolvedDromSlug,
        step: _SearchStep,
    ) -> tuple[str, str]:
        frame_type_id = None if step.region_scope == "rf" else slug.frame_type_id
        url = build_drom_search_url(
            criteria,
            make_slug=slug.make_slug,
            model_slug=slug.model_slug,
            frame_type_id=frame_type_id,
            region_scope=step.region_scope,
            year_tolerance=step.year_tolerance,
            relax_specs=step.relax_specs,
        )
        html = self._client.get_html(
            url,
            expected_path_parts=(
                f"/{slug.make_slug.lower()}/",
                f"/{slug.model_slug.lower()}/",
            ),
        )
        return html, url

    def _fetch_step(
        self,
        criteria: DromSearchCriteria,
        slug: ResolvedDromSlug,
        step: _SearchStep,
    ) -> tuple[FilteredMarketStats | None, str, ResolvedDromSlug]:
        try:
            html, url = self._fetch_step_html(criteria, slug, step)
        except DromNotFoundError:
            api_slug = self._slug_resolver.resolve_via_api(criteria.make, criteria.model)
            if api_slug is None or api_slug == slug:
                fallback_url = build_drom_search_url(
                    criteria,
                    make_slug=slug.make_slug,
                    model_slug=slug.model_slug,
                    frame_type_id=slug.frame_type_id,
                    region_scope=step.region_scope,
                    year_tolerance=step.year_tolerance,
                    relax_specs=step.relax_specs,
                )
                return None, fallback_url, slug
            slug = api_slug
            try:
                html, url = self._fetch_step_html(criteria, slug, step)
            except DromNotFoundError:
                fallback_url = build_drom_search_url(
                    criteria,
                    make_slug=slug.make_slug,
                    model_slug=slug.model_slug,
                    frame_type_id=slug.frame_type_id,
                    region_scope=step.region_scope,
                    year_tolerance=step.year_tolerance,
                    relax_specs=step.relax_specs,
                )
                return None, fallback_url, slug

        listings = parse_listings(html)
        return (
            filter_and_aggregate(listings, exclude_nearby_cities=(step.region_scope == "dfo")),
            url,
            slug,
        )


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
    if len(key) <= 450:
        return key
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"drom:market:hash:{digest}"


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
