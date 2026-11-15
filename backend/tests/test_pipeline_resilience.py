"""Unit tests for pipeline resilience fixes.

Covers auction house defaulting, Drom archive filtering, cascade fallbacks,
European/submodel slugs, antibot detection, EV power=None customs, and slider max.
"""

import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from apps.core.enums import AuctionHouse, FuelType
from apps.lots.customs import CurrencyRatesInput, CustomsInput, calculate_customs
from apps.lots.economics import (
    DEFAULT_BID_SLIDER_MAX_JPY,
    MAX_DYNAMIC_BID_SLIDER_MAX_JPY,
    compute_bid_slider_max_jpy,
    ensure_dynamic_bid_slider_max,
)
from apps.lots.integrations.drom.client import DromHttpClient
from apps.lots.integrations.drom.filtering import (
    build_drom_search_url,
    filter_and_aggregate,
    is_under_order_or_unavailable,
)
from apps.lots.integrations.drom.parser import is_antibot_challenge_html, parse_listings
from apps.lots.integrations.drom.schemas import DromBlockedError, DromSearchCriteria
from apps.lots.integrations.drom.service import DromMarketService
from apps.lots.integrations.drom.slugs import DromSlugResolver, ResolvedDromSlug
from apps.lots.integrations.ml.parser import (
    _DEFAULT_AUCTION_STRICTNESS,
    _MISSING_AUCTION_HOUSE_WARNING,
    _sheet_to_lot_fields,
)
from apps.lots.integrations.ml.schemas import NormalizedSheet, ParserResponse


def _ssr_html_with_groups(groups: list[dict]) -> bytes:
    payload = {
        "__slug": "bulls-list-auto",
        "bullList": {"bullsData": groups},
    }
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
        f"<body><script>{json.dumps(payload, ensure_ascii=False)}</script></body></html>"
    )
    return html.encode("utf-8")


def _html_response(content: bytes) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        content=content,
    )


def _bull(
    bull_id: int,
    price: int,
    *,
    title: str = "Lexus LS500, 2018",
    location: str = "Владивосток",
    sold: bool = False,
    car_state: list[str] | None = None,
) -> dict:
    return {
        "bullId": bull_id,
        "price": price,
        "url": f"https://auto.drom.ru/vladivostok/lexus/ls500/{bull_id}.html",
        "title": title,
        "description": "",
        "sold": sold,
        "carState": car_state or [],
        "location": location,
        "attributes": [{"type": "plain", "payload": "3.5 л"}],
    }


def test_ml_sheet_missing_auction_house_defaults_to_other() -> None:
    sheet = NormalizedSheet(
        lot_number="1001",
        make="Toyota",
        model="Corolla",
        frame_id="NRE210-1234567",
        overall_grade="4",
        auction_house=None,
        auction_strictness_index=None,
    )
    response = ParserResponse(status="ok", sheet=sheet)

    fields = _sheet_to_lot_fields(sheet, response, mapping_warnings=[])

    assert fields["auction_house"] == AuctionHouse.OTHER.value
    assert fields["auction_strictness_index"] == _DEFAULT_AUCTION_STRICTNESS
    assert _MISSING_AUCTION_HOUSE_WARNING in fields["ocr_warnings"]


def test_ml_sheet_unknown_auction_house_defaults_to_other_with_warning() -> None:
    sheet = NormalizedSheet(
        lot_number="1002",
        make="Toyota",
        model="Corolla",
        frame_id="NRE210-7654321",
        overall_grade="4",
        auction_house="MYSTERY_AUCTION",
        auction_strictness_index=None,
    )
    response = ParserResponse(status="ok", sheet=sheet)
    mapping_warnings: list[str] = []

    fields = _sheet_to_lot_fields(sheet, response, mapping_warnings=mapping_warnings)

    assert fields["auction_house"] == AuctionHouse.OTHER.value
    assert fields["auction_strictness_index"] == _DEFAULT_AUCTION_STRICTNESS
    assert any("auction_house" in w for w in fields["ocr_warnings"])


def test_drom_archive_group_excluded_even_when_sold_false() -> None:
    html = _ssr_html_with_groups(
        [
            {
                "title": None,
                "bulls": [_bull(1, 5_500_000), _bull(2, 5_800_000), _bull(3, 6_000_000)],
            },
            {"title": "Объявления в архиве", "bulls": [_bull(4, 2_100_000, sold=False)]},
        ]
    )
    listings = parse_listings(html)
    assert len(listings) == 4
    archived = next(item for item in listings if item.bull_id == "4")
    assert is_under_order_or_unavailable(archived) is True

    stats = filter_and_aggregate(listings)
    assert stats is not None
    assert stats.analogs_count == 3
    assert stats.filtered_out_under_order_count == 1
    assert stats.market_price_rf_rub == 5_800_000


def test_build_drom_search_url_supports_all_mileage_and_relaxed_engine() -> None:
    criteria = DromSearchCriteria(make="Lexus", model="LS500", year=2018, engine_cc=3444)

    all_mileage_url = build_drom_search_url(
        criteria,
        make_slug="lexus",
        model_slug="ls500",
        region_scope="rf",
        year_tolerance=2,
        relax_specs=True,
        without_rf_mileage_only=False,
        relax_engine_volume=True,
    )
    parsed = urlparse(all_mileage_url)
    params = parse_qs(parsed.query)

    assert "/bez-probega/" not in parsed.path
    assert parsed.path == "/lexus/ls500/"
    assert params["minyear"] == ["2016"]
    assert params["maxyear"] == ["2020"]
    assert "mv" not in params
    assert "xv" not in params


def test_drom_slug_resolver_handles_european_models_and_submodels() -> None:
    resolver = DromSlugResolver(
        DromHttpClient(transport=httpx.MockTransport(lambda _req: httpx.Response(404)))
    )

    mb_c200 = resolver.resolve("Mercedes", "C200")
    assert mb_c200 == ResolvedDromSlug("mercedes-benz", "c-class", None, is_fallback_guess=False)

    mb_glb = resolver.resolve("Mercedes-Benz", "GLB200d")
    assert mb_glb == ResolvedDromSlug("mercedes-benz", "glb", None, is_fallback_guess=False)

    bmw_320 = resolver.resolve("BMW", "320i")
    assert bmw_320 == ResolvedDromSlug("bmw", "3-series", None, is_fallback_guess=False)

    bmw_x5 = resolver.resolve("BMW", "X5 30d")
    assert bmw_x5 == ResolvedDromSlug("bmw", "x5", None, is_fallback_guess=False)

    impreza_g4 = resolver.resolve("Subaru", "Impreza G4")
    assert impreza_g4.make_slug == "subaru"
    assert impreza_g4.model_slug == "impreza"
    assert impreza_g4.frame_type_id == 10
    assert impreza_g4.is_fallback_guess is False


def test_is_antibot_challenge_html_distinguishes_empty_ssr_from_captcha() -> None:
    empty_ssr = _ssr_html_with_groups([{"title": None, "bulls": []}]).decode("utf-8")
    assert is_antibot_challenge_html(empty_ssr) is False

    captcha_html = (
        "<html><body><h1>Подтвердите, что вы не робот</h1><div>qrator</div></body></html>"
    )
    assert is_antibot_challenge_html(captcha_html) is True

    generic_block = "<html><body>Access denied. Please enable JavaScript and cookies.</body></html>"
    assert is_antibot_challenge_html(generic_block) is False


def test_cascade_uses_nearby_cities_dfo_when_primorye_sparse() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        html = _ssr_html_with_groups(
            [
                {"title": None, "bulls": [_bull(1, 5_600_000, location="Владивосток")]},
                {
                    "title": "Объявления в ближайших городах",
                    "bulls": [
                        _bull(2, 5_700_000, location="Хабаровск"),
                        _bull(3, 5_800_000, location="Благовещенск"),
                        _bull(4, 5_900_000, location="Южно-Сахалинск"),
                    ],
                },
            ]
        )
        return _html_response(html)

    service = DromMarketService(client=DromHttpClient(transport=httpx.MockTransport(handler)))
    criteria = DromSearchCriteria(make="Lexus", model="LS500", year=2018, engine_cc=3444)
    slug = service._slug_resolver.resolve(criteria.make, criteria.model)

    result, _ = service._search_live_cascade(criteria, slug)

    assert len(calls) == 1
    assert result is not None
    assert result.analogs_count == 4
    assert result.search_region_ru == "ДФО / Владивосток"
    assert result.is_fallback is True
    assert result.fallback_reason_ru is not None
    assert "ближайшие города" in result.fallback_reason_ru


def test_cascade_falls_back_to_all_mileage_when_bez_probega_empty() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        calls.append(url)
        if "/bez-probega/" in url:
            html = _ssr_html_with_groups([{"title": None, "bulls": []}])
        else:
            html = _ssr_html_with_groups(
                [
                    {
                        "title": None,
                        "bulls": [
                            _bull(10, 5_600_000),
                            _bull(11, 5_800_000),
                            _bull(12, 6_000_000),
                        ],
                    }
                ]
            )
        return _html_response(html)

    service = DromMarketService(client=DromHttpClient(transport=httpx.MockTransport(handler)))
    criteria = DromSearchCriteria(make="Lexus", model="LS500", year=2018, engine_cc=3444)
    slug = service._slug_resolver.resolve(criteria.make, criteria.model)

    result, _ = service._search_live_cascade(criteria, slug)

    assert result is not None
    assert result.analogs_count == 3
    assert result.market_price_rf_rub == 5_800_000
    assert result.is_fallback is True
    assert "/bez-probega/" not in result.drom_search_url
    assert len(calls) == 4


def test_cascade_resolves_via_api_on_empty_200_for_fallback_guessed_slug() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        calls.append(url)
        if "/unknown_c/" in url:
            html = _ssr_html_with_groups([{"title": None, "bulls": []}])
        else:
            html = _ssr_html_with_groups(
                [
                    {
                        "title": None,
                        "bulls": [_bull(1, 2_200_000), _bull(2, 2_400_000), _bull(3, 2_500_000)],
                    }
                ]
            )
        return _html_response(html)

    service = DromMarketService(client=DromHttpClient(transport=httpx.MockTransport(handler)))
    criteria = DromSearchCriteria(make="Mercedes-Benz", model="Unknown C", year=2020)
    guessed = ResolvedDromSlug("mercedes-benz", "unknown_c", None, is_fallback_guess=True)
    canonical = ResolvedDromSlug("mercedes-benz", "c-class", None, is_fallback_guess=False)

    with patch.object(
        service._slug_resolver, "resolve_via_api", return_value=canonical
    ) as mock_resolve:
        result, resolved_slug = service._search_live_cascade(criteria, guessed)

    assert result is not None
    assert result.analogs_count == 3
    assert resolved_slug.model_slug == "c-class"
    mock_resolve.assert_called_once_with("Mercedes-Benz", "Unknown C")


def test_cascade_raises_blocked_error_on_antibot_challenge_html() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            text="<html><body>SmartCaptcha: подтвердите, что вы не робот</body></html>",
        )

    service = DromMarketService(client=DromHttpClient(transport=httpx.MockTransport(handler)))
    criteria = DromSearchCriteria(make="Lexus", model="LS500", year=2018)
    slug = service._slug_resolver.resolve(criteria.make, criteria.model)

    with pytest.raises(DromBlockedError):
        service._search_live_cascade(criteria, slug)


def test_ev_customs_allows_missing_power_hp_with_zero_excise() -> None:
    result = calculate_customs(
        CustomsInput(
            engine_cc=0,
            fuel_type=FuelType.EV,
            power_hp=None,
            first_reg_year=2021,
            first_reg_month=5,
            customs_value_eur=18_000.0,
        ),
        CurrencyRatesInput(jpy_rub=0.55, eur_rub=100.0, usd_rub=92.0),
        on_date=date(2026, 5, 1),
    )

    assert result.customs_duty_rub == 270_000
    assert result.excise_rub == 0
    assert result.import_vat_rub > 0


def test_dynamic_bid_slider_max_jpy_scales_for_high_value_cars() -> None:
    assert (
        compute_bid_slider_max_jpy(market_price_rf_rub=1_200_000, jpy_rub=0.55)
        == DEFAULT_BID_SLIDER_MAX_JPY
    )
    assert compute_bid_slider_max_jpy(market_price_rf_rub=5_800_000, jpy_rub=0.55) == 10_600_000
    assert (
        compute_bid_slider_max_jpy(market_price_rf_rub=50_000_000, jpy_rub=0.5)
        == MAX_DYNAMIC_BID_SLIDER_MAX_JPY
    )

    unsaved_lot = SimpleNamespace(
        pk=None,
        market_price_rf_rub=5_800_000,
        auction_bid_jpy=None,
        bid_slider_max_jpy=2_500_000,
    )
    new_max = ensure_dynamic_bid_slider_max(unsaved_lot, jpy_rub=0.55)  # type: ignore[arg-type]
    assert new_max == 10_600_000
    assert unsaved_lot.bid_slider_max_jpy == 10_600_000
