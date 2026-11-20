"""Drom regional cascade executor and market-cache payload mappers."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from apps.integrations.drom.filtering import (
    FilteredMarketStats,
    build_drom_search_url,
    filter_and_aggregate,
)
from apps.integrations.drom.parser import parse_listings
from apps.integrations.drom.schemas import (
    DromBlockedError,
    DromBudgetExhaustedError,
    DromFetchError,
    DromMarketResult,
    DromNotFoundError,
    DromSearchCriteria,
)


def _same_slug(a: ResolvedDromSlug, b: ResolvedDromSlug) -> bool:
    return (a.make_slug, a.model_slug, a.frame_type_id) == (
        b.make_slug,
        b.model_slug,
        b.frame_type_id,
    )


if TYPE_CHECKING:
    from apps.integrations.drom.client import DromHttpClient
    from apps.integrations.drom.slugs import DromSlugResolver, ResolvedDromSlug

_MIN_ANALOGS_THRESHOLD = 3


@dataclass(frozen=True, slots=True)
class _SearchStep:
    region_scope: str
    region_label_ru: str
    year_tolerance: int
    relax_specs: bool
    is_fallback: bool
    fallback_reason_ru: str | None
    without_rf_mileage_only: bool = True
    relax_engine_volume: bool = False


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
    _SearchStep(
        region_scope="dfo",
        region_label_ru="ДФО / Владивосток",
        year_tolerance=1,
        relax_specs=True,
        is_fallback=True,
        fallback_reason_ru=(
            "Нет аналогов без пробега по РФ — выборка расширена на все объявления в ДФО (±1 год)"
        ),
        without_rf_mileage_only=False,
    ),
    _SearchStep(
        region_scope="rf",
        region_label_ru="Вся РФ",
        year_tolerance=2,
        relax_specs=True,
        is_fallback=True,
        fallback_reason_ru=(
            "Нет аналогов без пробега по РФ — выборка расширена на всю РФ "
            "(включая с пробегом по РФ, ±2 года)"
        ),
        without_rf_mileage_only=False,
    ),
    _SearchStep(
        region_scope="rf",
        region_label_ru="Вся РФ",
        year_tolerance=4,
        relax_specs=True,
        is_fallback=True,
        fallback_reason_ru=(
            "Редкая модель — выборка максимально расширена на всю РФ (±4 года, с пробегом по РФ)"
        ),
        without_rf_mileage_only=False,
        relax_engine_volume=True,
    ),
)


def build_market_candidate(
    stats: FilteredMarketStats,
    step: _SearchStep,
    used_url: str,
    *,
    used_nearby: bool = False,
) -> DromMarketResult:
    """Build a ``DromMarketResult`` snapshot from aggregated listing statistics."""
    is_fallback = step.is_fallback or used_nearby
    fallback_reason_ru = step.fallback_reason_ru
    if used_nearby:
        fallback_reason_ru = (
            f"{fallback_reason_ru}; учтены ближайшие города ДФО"
            if fallback_reason_ru
            else "Мало аналогов в Приморье — учтены ближайшие города ДФО"
        )
    return DromMarketResult(
        market_price_rf_rub=stats.market_price_rf_rub,
        analogs_count=stats.analogs_count,
        price_min_rub=stats.price_min_rub,
        price_max_rub=stats.price_max_rub,
        search_region_ru=step.region_label_ru,
        excludes_under_order=True,
        filtered_out_under_order_count=stats.filtered_out_under_order_count,
        is_fallback=is_fallback,
        fallback_reason_ru=fallback_reason_ru,
        drom_search_url=used_url,
    )


def build_step_url(
    criteria: DromSearchCriteria,
    slug: ResolvedDromSlug,
    step: _SearchStep,
) -> str:
    return build_drom_search_url(
        criteria,
        make_slug=slug.make_slug,
        model_slug=slug.model_slug,
        frame_type_id=slug.frame_type_id,
        region_scope=step.region_scope,
        year_tolerance=step.year_tolerance,
        relax_specs=step.relax_specs,
        without_rf_mileage_only=step.without_rf_mileage_only,
        relax_engine_volume=step.relax_engine_volume,
    )


def _pick_higher_analogs(
    current: DromMarketResult | None,
    candidate: DromMarketResult,
) -> DromMarketResult:
    if current is None or candidate.analogs_count > current.analogs_count:
        return candidate
    return current


class DromCascadeExecutor:
    """Executes Drom search steps across DFO/RF regions with slug-API fallback."""

    def __init__(self, client: DromHttpClient, slug_resolver: DromSlugResolver) -> None:
        self._client = client
        self._slug_resolver = slug_resolver

    def run(
        self,
        criteria: DromSearchCriteria,
        resolved_slug: ResolvedDromSlug,
    ) -> tuple[DromMarketResult | None, ResolvedDromSlug]:
        best_partial: DromMarketResult | None = None
        best_nearby: DromMarketResult | None = None
        current_slug = resolved_slug
        last_error: DromFetchError | None = None

        for step in _SEARCH_CASCADE:
            if (
                step.region_scope == "rf"
                and best_nearby is not None
                and best_nearby.analogs_count >= _MIN_ANALOGS_THRESHOLD
            ):
                return best_nearby, current_slug

            try:
                strict_stats, nearby_stats, used_url, current_slug = self.fetch_step(
                    criteria, current_slug, step
                )
            except DromBlockedError:
                if best_nearby is not None and best_nearby.analogs_count >= _MIN_ANALOGS_THRESHOLD:
                    return best_nearby, current_slug
                if best_partial is not None:
                    return best_partial, current_slug
                raise
            except DromFetchError as exc:
                last_error = exc
                if isinstance(exc, DromBudgetExhaustedError) or "budget" in str(exc).lower():
                    break
                continue

            winner, best_partial, best_nearby = self._evaluate_step_stats(
                step=step,
                used_url=used_url,
                strict_stats=strict_stats,
                nearby_stats=nearby_stats,
                best_partial=best_partial,
                best_nearby=best_nearby,
            )
            if winner is not None:
                return winner, current_slug

        if best_nearby is not None and best_nearby.analogs_count >= _MIN_ANALOGS_THRESHOLD:
            return best_nearby, current_slug
        if best_partial is None and last_error is not None:
            raise last_error
        return best_partial, current_slug

    @staticmethod
    def _evaluate_step_stats(
        *,
        step: _SearchStep,
        used_url: str,
        strict_stats: FilteredMarketStats | None,
        nearby_stats: FilteredMarketStats | None,
        best_partial: DromMarketResult | None,
        best_nearby: DromMarketResult | None,
    ) -> tuple[DromMarketResult | None, DromMarketResult | None, DromMarketResult | None]:
        if strict_stats is not None:
            candidate = build_market_candidate(strict_stats, step, used_url)
            if strict_stats.analogs_count >= _MIN_ANALOGS_THRESHOLD:
                return candidate, best_partial, best_nearby
            best_partial = _pick_higher_analogs(best_partial, candidate)

        if nearby_stats is not None:
            strict_count = strict_stats.analogs_count if strict_stats is not None else 0
            if nearby_stats.analogs_count > strict_count:
                nearby_candidate = build_market_candidate(
                    nearby_stats, step, used_url, used_nearby=True
                )
                best_nearby = _pick_higher_analogs(best_nearby, nearby_candidate)
                best_partial = _pick_higher_analogs(best_partial, nearby_candidate)
        return None, best_partial, best_nearby

    def _fetch_step_html(
        self,
        criteria: DromSearchCriteria,
        slug: ResolvedDromSlug,
        step: _SearchStep,
    ) -> tuple[str, str]:
        url = build_step_url(criteria, slug, step)
        html = self._client.get_html(
            url,
            expected_path_parts=(
                f"/{slug.make_slug.lower()}/",
                f"/{slug.model_slug.lower()}/",
            ),
        )
        return html, url

    def _retry_with_api_slug(
        self,
        criteria: DromSearchCriteria,
        slug: ResolvedDromSlug,
        step: _SearchStep,
    ) -> tuple[str | None, str | None, ResolvedDromSlug | None]:
        api_slug = self._slug_resolver.resolve_via_api(criteria.make, criteria.model)
        if api_slug is None or _same_slug(api_slug, slug):
            return None, None, None
        try:
            html, url = self._fetch_step_html(criteria, api_slug, step)
        except DromNotFoundError:
            return None, None, api_slug
        return html, url, api_slug

    def fetch_step(
        self,
        criteria: DromSearchCriteria,
        slug: ResolvedDromSlug,
        step: _SearchStep,
    ) -> tuple[FilteredMarketStats | None, FilteredMarketStats | None, str, ResolvedDromSlug]:
        try:
            html, url = self._fetch_step_html(criteria, slug, step)
        except DromNotFoundError:
            html_retry, url_retry, api_slug = self._retry_with_api_slug(criteria, slug, step)
            slug = api_slug if api_slug is not None else replace(slug, is_fallback_guess=False)
            if html_retry is None or url_retry is None:
                return None, None, build_step_url(criteria, slug, step), slug
            html, url = html_retry, url_retry

        listings = parse_listings(html)
        if not listings and slug.is_fallback_guess:
            html_retry, url_retry, api_slug = self._retry_with_api_slug(criteria, slug, step)
            slug = api_slug if api_slug is not None else replace(slug, is_fallback_guess=False)
            if html_retry is not None and url_retry is not None:
                html, url = html_retry, url_retry
                listings = parse_listings(html)
            else:
                return None, None, build_step_url(criteria, slug, step), slug

        if step.region_scope == "dfo":
            strict_stats = filter_and_aggregate(listings, exclude_nearby_cities=True)
            if strict_stats is not None and strict_stats.analogs_count >= _MIN_ANALOGS_THRESHOLD:
                return strict_stats, None, url, slug
            nearby_stats = filter_and_aggregate(listings, exclude_nearby_cities=False)
            return strict_stats, nearby_stats, url, slug

        return filter_and_aggregate(listings, exclude_nearby_cities=False), None, url, slug
