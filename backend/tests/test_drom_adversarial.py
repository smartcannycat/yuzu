import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

import httpx
import pytest
from django.db import connections
from django.utils import timezone

from apps.core.enums import (
    AgeCorridor,
    AuctionHouse,
    ChecklistItemStatus,
    CrossAuditStatus,
    DutyCalculationMode,
    ExternalCacheSource,
    FuelType,
    ItemProcessingStatus,
    OdometerStatus,
    PowerHpSource,
    RiskLevel,
    SystemKey,
    TaskStep,
    TrafficLightColor,
)
from apps.core.models import ExternalCache
from apps.lots import schemas
from apps.lots.integrations.drom.cache import read_drom_cache, write_drom_cache
from apps.lots.integrations.drom.client import DromHttpClient
from apps.lots.integrations.drom.filtering import (
    _remove_price_outliers,
    build_drom_search_url,
    filter_and_aggregate,
    is_under_order_or_unavailable,
)
from apps.lots.integrations.drom.parser import (
    parse_catalog_generations,
    parse_catalog_power_specs,
    parse_listings,
)
from apps.lots.integrations.drom.power import DromPowerResolver, normalize_katashiki_candidates
from apps.lots.integrations.drom.schemas import (
    DromBlockedError,
    DromFetchError,
    DromListing,
    DromSearchCriteria,
)
from apps.lots.integrations.drom.service import DromMarketService, _build_market_cache_key
from apps.lots.integrations.drom.slugs import DromSlugResolver, normalize_slug
from apps.lots.models import (
    Batch,
    BatchItem,
    CrossAuditReport,
    CurrencyRatesSnapshot,
    CustomsCalculation,
    FarpostRepairSummary,
    Lot,
    LotRiskFlags,
    MarketComparisonInfo,
    SafetyCheckItem,
    SafetyChecklist,
    TrafficLightVerdict,
    WiseCostLadder,
    WiseCostStep,
)
from apps.lots.services import _build_lot_detail, _step_drom_market


def _make_ssr_html(bulls: list[dict], *, charset: str = "utf-8") -> bytes:
    payload = {
        "__slug": "bulls-list-auto",
        "bullList": {
            "bullsData": [
                {
                    "title": None,
                    "bulls": bulls,
                }
            ]
        },
    }
    html = (
        f'<!DOCTYPE html><html><head><meta charset="{charset}"></head>'
        f"<body><script>{json.dumps(payload, ensure_ascii=False)}</script></body></html>"
    )
    return html.encode(charset)


def _bull(
    bull_id: int | str | None,
    price: object,
    *,
    title: str = "Toyota Corolla, 2020",
    description: str = "",
    sold: bool = False,
    car_state: list[str] | None = None,
    info: str | None = None,
    location: str = "Владивосток",
) -> dict:
    raw: dict = {
        "bullId": bull_id,
        "price": price,
        "url": f"https://auto.drom.ru/vladivostok/toyota/corolla/{bull_id}.html",
        "title": title,
        "description": description,
        "sold": sold,
        "carState": car_state or [],
        "location": location,
        "attributes": [{"type": "plain", "payload": "1.2 л (116 л.с.)"}],
    }
    if info is not None:
        raw["info"] = info
    return raw


# ---------------------------------------------------------------------------
# 1. Parser edge cases: malformed/truncated JSON, empty HTML, price anomalies
# ---------------------------------------------------------------------------


def test_parse_listings_malformed_json_falls_back_to_dom() -> None:
    html = """
    <html><body>
      <script>{"__slug": "bulls-list-auto", "bullList": {"bullsData": [TRUNCATED</script>
      <div data-ftid="bulls-list_bull">
        <div data-ftid="bull_title"><a href="https://auto.drom.ru/10.html">Toyota Corolla</a></div>
        <div data-ftid="bull_price">1 490 000 ₽</div>
        <div data-ftid="bull_location">Владивосток</div>
      </div>
    </body></html>
    """
    listings = parse_listings(html)
    assert len(listings) == 1
    assert listings[0].price_rub == 1490000
    assert listings[0].title == "Toyota Corolla"


def test_parse_listings_empty_html_and_missing_or_zero_prices() -> None:
    assert parse_listings("") == []
    assert parse_listings("   \n\t  ") == []

    dom_bad_prices = """
    <html><body>
      <div data-ftid="bulls-list_bull">
        <div data-ftid="bull_title">No price element</div>
      </div>
      <div data-ftid="bulls-list_bull">
        <div data-ftid="bull_title">Zero price</div>
        <div data-ftid="bull_price">0 ₽</div>
      </div>
      <div data-ftid="bulls-list_bull">
        <div data-ftid="bull_title">Non numeric price</div>
        <div data-ftid="bull_price">Договорная</div>
      </div>
    </body></html>
    """
    assert parse_listings(dom_bad_prices) == []

    ssr_bad = _make_ssr_html(
        [
            _bull(1, 0),
            _bull(2, -1500000),
            _bull(3, None),
            _bull(4, "По запросу"),
            _bull(5, ""),
        ]
    ).decode("utf-8")
    assert parse_listings(ssr_bad) == []


def test_parse_listings_rejects_negative_price_strings_and_booleans() -> None:
    ssr_tricky = _make_ssr_html(
        [
            _bull(1, "-1500000"),
            _bull(2, "-500 000 ₽"),
            _bull(3, True),
        ]
    ).decode("utf-8")
    assert parse_listings(ssr_tricky) == []

    dom_negative = """
    <html><body>
      <div data-ftid="bulls-list_bull">
        <div data-ftid="bull_title">Negative DOM price</div>
        <div data-ftid="bull_price">-1 200 000 ₽</div>
      </div>
    </body></html>
    """
    assert parse_listings(dom_negative) == []


def test_parse_listings_decimal_price_string_not_inflated() -> None:
    ssr_decimal = _make_ssr_html([_bull(1, "1 500 000.00 ₽")]).decode("utf-8")
    listings = parse_listings(ssr_decimal)
    assert len(listings) == 1
    assert listings[0].price_rub == 1500000


# ---------------------------------------------------------------------------
# 2. Filtering: carState / badges / description / title & Yo/E variants
# ---------------------------------------------------------------------------


def test_filtering_mixed_case_yo_variants_and_all_rejected() -> None:
    listings = [
        DromListing("1", "Toyota Corolla ПОЛНАЯ ПОШЛИНА", 1400000, car_state=["ПОД ЗАКАЗ"]),
        DromListing("2", "Corolla", 1450000, badges=["Привезем из Японии"]),
        DromListing("3", "Corolla", 1480000, description="Привезём под ПТС в любой город"),
        DromListing("4", "Corolla в пути", 1500000),
        DromListing("5", "Corolla", 1520000, attributes=["В НАЛИЧИИ В КОРЕЕ"]),
        DromListing("6", "Corolla", 1550000, sold=True),
    ]
    assert all(is_under_order_or_unavailable(item) for item in listings)
    assert filter_and_aggregate(listings) is None


def test_dom_fallback_catches_in_transit_and_import_badges() -> None:
    dom_html = """
    <html><body>
      <div data-ftid="bulls-list_bull">
        <div data-ftid="bull_title"><a href="https://auto.drom.ru/1.html">Honda Vezel</a></div>
        <div data-ftid="bull_price">1 600 000 ₽</div>
        <span>В пути</span>
      </div>
      <div data-ftid="bulls-list_bull">
        <div data-ftid="bull_title"><a href="https://auto.drom.ru/2.html">Honda Vezel</a></div>
        <div data-ftid="bull_price">1 550 000 ₽</div>
        <div>Привезём с аукциона</div>
      </div>
    </body></html>
    """
    listings = parse_listings(dom_html)
    assert filter_and_aggregate(listings) is None


def test_filtering_does_not_reject_in_stock_car_mentioning_auction_sheet() -> None:
    listing = DromListing(
        "10",
        "Toyota Corolla, 2020",
        1520000,
        description="В наличии во Владивостоке. Есть оригинальный аукционный лист 4.5 балла.",
    )
    assert is_under_order_or_unavailable(listing) is False


# ---------------------------------------------------------------------------
# 3. Outlier removal & cascade edge cases
# ---------------------------------------------------------------------------


def test_outlier_removal_small_samples_and_decoy_and_identical() -> None:
    # 1, 2, 3 listings -> no IQR filtering
    one = filter_and_aggregate([DromListing("1", "A", 1500000)])
    assert one is not None
    assert (one.analogs_count, one.market_price_rf_rub, one.price_min_rub, one.price_max_rub) == (
        1,
        1500000,
        1500000,
        1500000,
    )

    two = filter_and_aggregate([DromListing("1", "A", 500000), DromListing("2", "A", 1500000)])
    assert two is not None
    assert two.analogs_count == 2
    assert two.market_price_rf_rub == 1000000

    three = filter_and_aggregate(
        [
            DromListing("1", "A", 400000),
            DromListing("2", "A", 1500000),
            DromListing("3", "A", 1600000),
        ]
    )
    assert three is not None
    assert three.analogs_count == 3
    assert three.market_price_rf_rub == 1500000

    # 4 identical prices (iqr == 0)
    identical = filter_and_aggregate([DromListing(str(i), "A", 1500000) for i in range(4)])
    assert identical is not None
    assert identical.analogs_count == 4
    assert identical.market_price_rf_rub == 1500000
    assert identical.filtered_out_under_order_count == 0

    # Decoy < 55% of median is filtered out
    with_decoy = filter_and_aggregate(
        [
            DromListing("1", "A", 700000),
            DromListing("2", "A", 1500000),
            DromListing("3", "A", 1550000),
            DromListing("4", "A", 1600000),
            DromListing("5", "A", 1650000),
        ]
    )
    assert with_decoy is not None
    assert with_decoy.analogs_count == 4
    assert with_decoy.price_min_rub == 1500000
    assert with_decoy.filtered_out_under_order_count == 1

    # Direct check of _remove_price_outliers returns non-empty list for extreme splits
    kept, removed = _remove_price_outliers([100, 100, 10000, 10000])
    assert kept
    assert removed >= 0


def test_outlier_removal_upper_spike_when_iqr_is_zero() -> None:
    listings = [
        DromListing("1", "A", 1500000),
        DromListing("2", "A", 1500000),
        DromListing("3", "A", 1500000),
        DromListing("4", "A", 1500000),
        DromListing("5", "A", 15000000),  # 10x typo/outlier when IQR == 0
    ]
    stats = filter_and_aggregate(listings)
    assert stats is not None
    assert stats.analogs_count == 4
    assert stats.price_max_rub == 1500000


@pytest.mark.django_db
def test_cascade_zero_analogs_falls_back_to_stale_then_reference_then_error() -> None:
    calls: list[str] = []

    def all_under_order_handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            content=_make_ssr_html([_bull(1, 1200000, car_state=["под заказ"])]),
        )

    service = DromMarketService(
        client=DromHttpClient(transport=httpx.MockTransport(all_under_order_handler))
    )
    criteria = DromSearchCriteria(make="Toyota", model="Corolla", year=2020, engine_cc=1196)

    # Without cache, 3 cascade steps yield 0 in-stock -> reference fallback
    ref_result = service.evaluate(criteria)
    search_calls = [u for u in calls if "auto.drom.ru" in u]
    assert len(search_calls) == 3
    assert ref_result.is_fallback is True
    assert ref_result.market_price_rf_rub == 1520000

    # With stale cache -> prefers stale cache over reference fallback
    resolved_slug = DromSlugResolver(service._client).resolve(criteria.make, criteria.model)
    ExternalCache.objects.create(
        key=_build_market_cache_key(criteria, resolved_slug),
        source=ExternalCacheSource.DROM,
        payload={
            "market_price_rf_rub": 1444000,
            "analogs_count": 5,
            "price_min_rub": 1350000,
            "price_max_rub": 1550000,
            "search_region_ru": "ДФО / Владивосток",
            "excludes_under_order": True,
            "filtered_out_under_order_count": 1,
            "is_fallback": False,
            "fallback_reason_ru": None,
            "drom_search_url": "https://auto.drom.ru/region25/toyota/corolla/bez-probega/",
        },
        expires_at=timezone.now() - timedelta(hours=1),
    )
    calls.clear()
    stale_result = service.evaluate(criteria)
    stale_search_calls = [u for u in calls if "auto.drom.ru" in u]
    assert len(stale_search_calls) == 3
    assert stale_result.is_fallback is True
    assert stale_result.market_price_rf_rub == 1444000

    # Unknown model with 0 in-stock and no cache -> DromFetchError
    with pytest.raises(DromFetchError):
        service.evaluate(DromSearchCriteria(make="Mitsuoka", model="Galue", year=2018))


@pytest.mark.django_db
def test_cascade_keeps_best_partial_when_less_than_three() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "region25" in url and "minyear=2020&maxyear=2020" in url:
            bulls = [_bull(1, 1500000), _bull(2, 1560000)]
        elif "region25" in url and "minyear=2019&maxyear=2021" in url:
            bulls = [_bull(1, 1450000)]
        else:
            bulls = []
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            content=_make_ssr_html(bulls),
        )

    service = DromMarketService(client=DromHttpClient(transport=httpx.MockTransport(handler)))
    result = service.evaluate(DromSearchCriteria(make="Toyota", model="Corolla", year=2020))
    assert result.analogs_count == 2
    assert result.market_price_rf_rub == 1530000
    assert result.search_region_ru == "ДФО / Владивосток"
    assert result.is_fallback is False


# ---------------------------------------------------------------------------
# 4. DromSearchCriteria, slugs, and URL validity / length
# ---------------------------------------------------------------------------


def test_build_drom_search_url_handles_none_zero_transmission_and_drive() -> None:
    ev_criteria = DromSearchCriteria(
        make="Nissan",
        model="Leaf",
        year=None,
        engine_cc=0,
        model_code=None,
        transmission="CVT",
        drive_type="2WD",
    )
    ev_url = build_drom_search_url(ev_criteria, make_slug="nissan", model_slug="leaf")
    assert "minyear" not in ev_url
    assert "maxyear" not in ev_url
    assert "mv=" not in ev_url
    assert "xv=" not in ev_url
    assert "transmission" not in ev_url
    assert "privod" not in ev_url
    assert len(ev_url) <= 500

    none_cc = DromSearchCriteria(
        make="Honda",
        model="Vezel",
        year=2022,
        engine_cc=None,
        transmission="AT",
        drive_type="4WD",
    )
    url_4wd = build_drom_search_url(none_cc, make_slug="honda", model_slug="vezel")
    assert "mv=" not in url_4wd
    assert "privod%5B%5D=3" in url_4wd
    assert "transmission" not in url_4wd

    relaxed_url = build_drom_search_url(
        none_cc, make_slug="honda", model_slug="vezel", relax_specs=True
    )
    assert "privod" not in relaxed_url


def test_transmission_detection_amt_false_positive_and_cyrillic_mt() -> None:
    amt = DromSearchCriteria(make="Toyota", model="Yaris", year=2020, transmission="AMT")
    amt_url = build_drom_search_url(amt, make_slug="toyota", model_slug="yaris")
    assert "transmission%5B%5D=1" not in amt_url

    cyrillic_mt = DromSearchCriteria(make="Toyota", model="Corolla", year=2020, transmission="6МТ")
    cyr_url = build_drom_search_url(cyrillic_mt, make_slug="toyota", model_slug="corolla")
    assert "transmission%5B%5D=1" in cyr_url


def test_slug_handling_weird_characters_cyrillic_and_url_length() -> None:
    resolver = DromSlugResolver(DromHttpClient())
    slash_slug = resolver.resolve("Toyota", "Corolla / Fielder")
    assert slash_slug.make_slug == "toyota"
    assert slash_slug.model_slug == "corolla_fielder"

    hyphen_slug = resolver.resolve("Nissan", "X-Trail")
    assert hyphen_slug.model_slug == "x-trail"

    # Pure Cyrillic make/model should not yield empty path segments ("///")
    cyr_slug = resolver.resolve("Тойота", "Королла")
    assert cyr_slug.make_slug != ""
    assert cyr_slug.model_slug != ""

    # Extremely long make/model must still produce URL <= 500 chars for DB URLField(max_length=500)
    long_make = "a" * 240
    long_model = "b" * 240
    long_url = build_drom_search_url(
        DromSearchCriteria(make=long_make, model=long_model, year=2020, engine_cc=1500),
        make_slug=normalize_slug(long_make),
        model_slug=normalize_slug(long_model),
    )
    assert len(long_url) <= 500


# ---------------------------------------------------------------------------
# 5. power_hp resolution edge cases
# ---------------------------------------------------------------------------


def test_normalize_katashiki_candidates_prefix_and_body_letter() -> None:
    assert normalize_katashiki_candidates("6AA-RV5") == ["6AA-RV5", "RV5"]
    assert normalize_katashiki_candidates("DBA-RU3") == ["DBA-RU3", "RU3"]
    assert normalize_katashiki_candidates("3BA-NRE210W") == ["3BA-NRE210W", "NRE210W", "NRE210"]
    assert normalize_katashiki_candidates(None) == []
    assert normalize_katashiki_candidates("   ") == []


@pytest.mark.django_db
def test_power_hp_conflicting_specs_and_ev_zero_cc() -> None:
    # No HTTP calls should happen when mocking 404 for catalog
    def not_found(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = DromHttpClient(transport=httpx.MockTransport(not_found))
    resolver = DromPowerResolver(client, DromSlugResolver(client))

    # NRE210W in katashiki_power.json is 1196 cc gasoline -> conflicting 2500 cc must reject it
    res_bad_cc = resolver.resolve(
        make="Toyota",
        model="Corolla",
        model_code="3BA-NRE210W",
        engine_cc=2500,
        fuel_type="gasoline",
    )
    assert res_bad_cc.power_hp is None

    # Conflicting fuel_type must reject it
    res_bad_fuel = resolver.resolve(
        make="Toyota",
        model="Corolla",
        model_code="3BA-NRE210W",
        engine_cc=1196,
        fuel_type="hybrid",
    )
    assert res_bad_fuel.power_hp is None

    # ZE1 in katashiki_power.json has engine_cc=0, fuel_type="ev" -> 2000 cc must NOT match ZE1
    res_ze1_bad_cc = resolver.resolve(
        make="Nissan",
        model="Leaf",
        model_code="ZE1",
        engine_cc=2000,
        fuel_type=None,
    )
    assert res_ze1_bad_cc.power_hp is None


@pytest.mark.django_db
def test_power_hp_drom_catalog_substring_ambiguity_e12_vs_he12() -> None:
    model_html = """
    <html><body>
      <a href="/catalog/nissan/note/g_2016_1/">Note E12 / HE12 (E12, NE12, HE12)</a>
    </body></html>
    """
    gen_html = """
    <html><body>
      <table>
        <tr>
          <td>1.2 л, 79 л.с., бензин, вариатор, передний привод</td>
          <td>Кузов: DBA-E12</td>
        </tr>
        <tr><td>09.2012 - 11.2020</td></tr>
        <tr>
          <td>1.2 л, 109 л.с., гибрид, вариатор, передний привод</td>
          <td>Кузов: DAA-HE12</td>
        </tr>
        <tr><td>11.2016 - 11.2020</td></tr>
      </table>
    </body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/catalog/nissan/note/"):
            return httpx.Response(200, text=model_html)
        if url.endswith("/catalog/nissan/note/g_2016_1/"):
            return httpx.Response(200, text=gen_html)
        return httpx.Response(404)

    assert len(parse_catalog_generations(model_html, model_code="E12")) == 1
    assert len(parse_catalog_power_specs(gen_html)) == 2

    client = DromHttpClient(transport=httpx.MockTransport(handler))
    resolver = DromPowerResolver(client, DromSlugResolver(client))
    # Force catalog path with an unknown prefix/model_code or test catalog lookup directly:
    # Note: katashiki_power.json has E12=79, so call _lookup_drom_catalog directly to test
    # catalog disambiguation between DBA-E12 (79 hp) and DAA-HE12 (109 hp) when fuel_type=None.
    catalog_res = resolver._lookup_drom_catalog(
        make="Nissan",
        model="Note",
        model_code="E12",
        engine_cc=1198,
        fuel_type=None,
        drive_type="2WD",
        year=2018,
    )
    assert catalog_res is not None
    assert catalog_res.power_hp == 79


@pytest.mark.django_db
def test_step_drom_market_preserves_manual_power_hp(user_factory) -> None:
    user = user_factory(email="manual_hp@example.com")
    batch = Batch.objects.create(user=user)
    lot = Lot.objects.create(
        user=user,
        make="Toyota",
        model="Corolla Touring",
        model_code="3BA-NRE210W",
        year=2020,
        engine_cc=1196,
        power_hp=150,
        power_hp_source=PowerHpSource.MANUAL,
        is_under_160_hp=True,
    )
    item = BatchItem.objects.create(
        batch=batch,
        lot=lot,
        file_index=0,
        original_filename="manual.jpg",
        status=ItemProcessingStatus.PROCESSING,
        current_step=TaskStep.DROM_MARKET,
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            content=_make_ssr_html([_bull(1, 1500000), _bull(2, 1550000), _bull(3, 1600000)]),
        )

    mock_service = DromMarketService(client=DromHttpClient(transport=httpx.MockTransport(handler)))
    with patch("apps.lots.services.DromMarketService", return_value=mock_service):
        assert _step_drom_market(item) is True

    lot.refresh_from_db()
    assert lot.power_hp == 150
    assert lot.power_hp_source == PowerHpSource.MANUAL
    assert lot.is_under_160_hp is True
    assert lot.market_price_rf_rub == 1550000


# ---------------------------------------------------------------------------
# 6. HTTP client edge cases: 502/503 retries, 429 no-retry, encoding, timeout
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("retry_status", [502, 503])
def test_http_client_retries_502_503_and_succeeds_on_attempt_2(retry_status: int) -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(retry_status, text="Bad Gateway")
        return httpx.Response(200, text="<html>ok</html>")

    client = DromHttpClient(
        max_retries=1,
        retry_backoff_sec=0.0,
        transport=httpx.MockTransport(handler),
    )
    html = client.get_html("https://auto.drom.ru/test")
    assert attempts == 2
    assert "ok" in html


def test_http_client_429_immediately_raises_blocked_without_retry() -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(429, text="Too Many Requests")

    client = DromHttpClient(
        max_retries=3,
        retry_backoff_sec=0.0,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(DromBlockedError):
        client.get_html("https://auto.drom.ru/test")
    assert attempts == 1


def test_http_client_decodes_utf8_and_cp1251_and_handles_timeout() -> None:
    cp1251_bytes = "<html><head><meta charset='windows-1251'></head><body>Владивосток</body></html>"
    utf8_bytes = "<html><head></head><body>Владивосток</body></html>"

    def encoding_handler(request: httpx.Request) -> httpx.Response:
        if "cp1251" in str(request.url):
            return httpx.Response(
                200,
                headers={"Content-Type": "text/html"},
                content=cp1251_bytes.encode("cp1251"),
            )
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            content=utf8_bytes.encode("utf-8"),
        )

    client = DromHttpClient(transport=httpx.MockTransport(encoding_handler))
    assert "Владивосток" in client.get_html("https://auto.drom.ru/cp1251")
    assert "Владивосток" in client.get_html("https://auto.drom.ru/utf8")

    timeout_attempts = 0

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        nonlocal timeout_attempts
        timeout_attempts += 1
        raise httpx.ReadTimeout("timed out", request=request)

    timeout_client = DromHttpClient(
        max_retries=1,
        retry_backoff_sec=0.0,
        transport=httpx.MockTransport(timeout_handler),
    )
    with pytest.raises(DromFetchError):
        timeout_client.get_html("https://auto.drom.ru/slow")
    assert timeout_attempts == 2


# ---------------------------------------------------------------------------
# 7. Cache key uniqueness & concurrency
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_cache_key_uniqueness_for_drive_type_and_transmission() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "transmission%5B%5D=1" in url:
            price = 1400000
        elif "privod%5B%5D=3" in url:
            price = 1700000
        else:
            price = 1550000
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            content=_make_ssr_html([_bull(1, price), _bull(2, price), _bull(3, price)]),
        )

    service = DromMarketService(client=DromHttpClient(transport=httpx.MockTransport(handler)))

    res_2wd = service.evaluate(
        DromSearchCriteria(
            make="Toyota", model="Corolla", year=2020, engine_cc=1196, drive_type="2WD"
        )
    )
    res_4wd = service.evaluate(
        DromSearchCriteria(
            make="Toyota", model="Corolla", year=2020, engine_cc=1196, drive_type="4WD"
        )
    )
    assert res_2wd.market_price_rf_rub == 1550000
    assert res_4wd.market_price_rf_rub == 1700000

    res_6mt = service.evaluate(
        DromSearchCriteria(
            make="Toyota",
            model="Corolla",
            year=2020,
            engine_cc=1196,
            drive_type="2WD",
            transmission="6MT",
        )
    )
    res_cvt = service.evaluate(
        DromSearchCriteria(
            make="Toyota",
            model="Corolla",
            year=2020,
            engine_cc=1196,
            drive_type="2WD",
            transmission="CVT",
        )
    )
    assert res_6mt.market_price_rf_rub == 1400000
    assert res_cvt.market_price_rf_rub == 1550000
    assert "transmission" not in res_cvt.drom_search_url


@pytest.mark.django_db(transaction=True)
def test_concurrent_write_drom_cache_and_step_drom_market(user_factory) -> None:
    key = "drom:market:concurrent:test"

    def write_worker(idx: int) -> None:
        try:
            write_drom_cache(key, {"val": idx}, ttl=timedelta(minutes=5))
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(write_worker, range(12)))

    cached = read_drom_cache(key, allow_stale=False)
    assert cached is not None
    assert "val" in cached

    user = user_factory(email="concurrent_step@example.com")
    batch = Batch.objects.create(user=user)
    items: list[BatchItem] = []
    for i in range(4):
        lot = Lot.objects.create(
            user=user,
            make="Toyota",
            model="Corolla Touring",
            model_code="3BA-NRE210W",
            year=2020,
            engine_cc=1196,
            drive_type="2WD",
        )
        items.append(
            BatchItem.objects.create(
                batch=batch,
                lot=lot,
                file_index=i,
                original_filename=f"lot_{i}.jpg",
                status=ItemProcessingStatus.PROCESSING,
                current_step=TaskStep.DROM_MARKET,
            )
        )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            content=_make_ssr_html([_bull(1, 1500000), _bull(2, 1520000), _bull(3, 1540000)]),
        )

    def step_worker(batch_item: BatchItem) -> bool:
        try:
            service = DromMarketService(
                client=DromHttpClient(transport=httpx.MockTransport(handler))
            )
            with patch("apps.lots.services.DromMarketService", return_value=service):
                return _step_drom_market(batch_item)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(step_worker, items))

    assert outcomes == [True, True, True, True]
    assert MarketComparisonInfo.objects.filter(lot__user=user).count() == 4


# ---------------------------------------------------------------------------
# 8. Full Lot serialization & API_DATA_CONTRACTS.md validation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_full_lot_step_drom_market_and_contract_serialization(user_factory) -> None:
    user = user_factory(email="contract_lot@example.com")
    batch = Batch.objects.create(user=user)
    lot = Lot.objects.create(
        user=user,
        completed_at=timezone.now(),
        lot_number="3142",
        auction_house=AuctionHouse.TAA,
        auction_branch="TAA Chubu",
        auction_strictness_index=1.0,
        make="Toyota",
        model="Corolla Touring",
        trim="W×B",
        model_code="3BA-NRE210W",
        chassis_number="NRE210-2005418",
        frame_id="NRE210-2005418",
        frame_id_confidence="exact",
        first_reg_year=2020,
        first_reg_month=10,
        first_reg_date_str="10.2020 (3-5 лет, ЕАЭС)",
        is_pass_corridor_3_5=True,
        year=2020,
        engine_cc=1196,
        mileage_km=58240,
        odometer_status=OdometerStatus.CONFIRMED,
        transmission="6MT",
        drive_type="2WD",
        fuel_type=FuelType.GASOLINE,
        overall_grade="3.5",
        turnkey_cost_rub=1104899,
        net_benefit_rub=415101,
        benefit_percentage=37.6,
        verdict=TrafficLightColor.GREEN,
        verdict_headline="РЕКОМЕНДОВАНО К ПОКУПКЕ",
    )
    LotRiskFlags.objects.create(lot=lot)
    TrafficLightVerdict.objects.create(
        lot=lot,
        verdict=TrafficLightColor.GREEN,
        headline="РЕКОМЕНДОВАНО К ПОКУПКЕ",
        short_verdict_label="РЕКОМЕНДОВАНО",
        badge_text="Выгода: +415 101 ₽",
        net_benefit_rub=415101,
        benefit_percentage=37.6,
        body_summary_ru="Хорошее состояние",
        interior_summary_ru="Чистый салон",
    )
    CrossAuditReport.objects.create(
        lot=lot,
        status=CrossAuditStatus.CLEAN,
        risk_level=RiskLevel.CLEAN,
        has_critical_anomaly=False,
        headline_ru="Расхождений не найдено",
        times_auctioned=1,
    )
    checklist = SafetyChecklist.objects.create(
        lot=lot,
        overall_status=ChecklistItemStatus.OK,
        overall_label_ru="В норме",
    )
    SafetyCheckItem.objects.create(
        checklist=checklist,
        system_key=SystemKey.STRUCTURAL_FRAME,
        label_ru="Силовой каркас",
        status=ChecklistItemStatus.OK,
        detail_ru="Замечаний нет",
    )
    customs = CustomsCalculation.objects.create(
        lot=lot,
        age_corridor=AgeCorridor.THREE_TO_FIVE_YEARS,
        duty_calculation_mode=DutyCalculationMode.EUR_PER_CC,
        engine_cc=1196,
        duty_rate_eur_per_cc=1.7,
        customs_duty_eur=2033.2,
        customs_duty_rub=193154,
        is_under_160_hp=True,
        is_commercial_util=False,
        utilization_fee_rub=5200,
        customs_clearance_fee_rub=4268,
        freight_vladivostok_rub=95000,
        broker_svh_sbkts_rub=43835,
        meti_sanction_risk=False,
    )
    CurrencyRatesSnapshot.objects.create(
        customs=customs,
        jpy_rub_bank=0.642,
        eur_rub_cbrf=95.0,
        usd_rub_cbrf=88.0,
        cbrf_date="13.11.2026",
    )
    FarpostRepairSummary.objects.create(lot=lot)
    ladder = WiseCostLadder.objects.create(
        lot=lot,
        car_bid_jpy=780000,
        car_bid_rub=500760,
        turnkey_cost_rub=1104899,
        market_price_rf_rub=1520000,
        net_benefit_rub=415101,
        benefit_percentage=37.6,
    )
    WiseCostStep.objects.create(
        ladder=ladder,
        step_number=1,
        name_ru="Ставка на аукционе",
        amount_rub=500760,
        original_currency="JPY",
        original_amount=780000.0,
    )
    item = BatchItem.objects.create(
        batch=batch,
        lot=lot,
        file_index=0,
        original_filename="corolla.jpg",
        status=ItemProcessingStatus.PROCESSING,
        current_step=TaskStep.DROM_MARKET,
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            content=_make_ssr_html(
                [
                    _bull(1, 1490000),
                    _bull(2, 1520000),
                    _bull(3, 1580000),
                    _bull(4, 1300000, car_state=["под заказ"]),
                ]
            ),
        )

    mock_service = DromMarketService(client=DromHttpClient(transport=httpx.MockTransport(handler)))
    with patch("apps.lots.services.DromMarketService", return_value=mock_service):
        assert _step_drom_market(item) is True

    lot.refresh_from_db()
    market_schema = schemas.MarketComparisonInfo.model_validate(lot.market_info)
    assert market_schema.market_price_rf_rub == 1520000
    assert market_schema.analogs_count == 3
    assert market_schema.price_min_rub == 1490000
    assert market_schema.price_max_rub == 1580000
    assert market_schema.excludes_under_order is True
    assert market_schema.filtered_out_under_order_count == 1
    assert market_schema.is_fallback is False
    assert market_schema.fallback_reason_ru is None
    assert len(market_schema.drom_search_url) <= 500
    assert market_schema.drom_search_url == lot.market_info.drom_search_url

    detail = _build_lot_detail(lot)
    assert isinstance(detail, schemas.LotDetailResponse)
    dumped = detail.model_dump(mode="json")
    assert dumped["market"] == market_schema.model_dump(mode="json")
    assert dumped["media"]["drom_search_url"] == market_schema.drom_search_url
    assert dumped["passport"]["power_hp"] == 116
    assert dumped["passport"]["power_hp_source"] == "katashiki_cache"
    assert dumped["passport"]["is_under_160_hp"] is True
