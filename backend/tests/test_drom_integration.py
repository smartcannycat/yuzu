import json
from datetime import timedelta
from unittest.mock import patch

import httpx
import pytest
from django.utils import timezone

from apps.core.enums import (
    ExternalCacheSource,
    ItemProcessingStatus,
    PowerHpSource,
    TaskStep,
)
from apps.core.models import ExternalCache
from apps.lots.integrations.drom.client import DromHttpClient
from apps.lots.integrations.drom.filtering import (
    build_drom_search_url,
    filter_and_aggregate,
)
from apps.lots.integrations.drom.parser import (
    parse_catalog_generations,
    parse_catalog_power_specs,
    parse_listings,
)
from apps.lots.integrations.drom.schemas import (
    DromFetchError,
    DromListing,
    DromSearchCriteria,
)
from apps.lots.integrations.drom.service import DromMarketService, _build_market_cache_key
from apps.lots.integrations.drom.slugs import DromSlugResolver
from apps.lots.models import Batch, BatchItem, Lot, MarketComparisonInfo
from apps.lots.services import _step_drom_market


def _make_ssr_json_html(bulls: list[dict]) -> bytes:
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
        "filter": {"filledParams": {}},
    }
    html = (
        "<!DOCTYPE html><html><head>"
        '<meta http-equiv="Content-Type" content="text/html; charset=windows-1251">'
        "</head><body>"
        f"<script>{json.dumps(payload, ensure_ascii=False)}</script>"
        "</body></html>"
    )
    return html.encode("cp1251")


def _bull(
    bull_id: int,
    price: int,
    *,
    title: str = "Toyota Corolla, 2020",
    description: str = "",
    sold: bool = False,
    car_state: list[str] | None = None,
    location: str = "Владивосток",
) -> dict:
    return {
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


def test_parse_listings_decodes_cp1251_json_and_falls_back_to_html() -> None:
    raw = _make_ssr_json_html(
        [
            _bull(101, 1520000, description="Отличное состояние, в наличии во Владивостоке"),
            _bull(102, 1480000, car_state=["под заказ"]),
        ]
    )
    html_text = raw.decode("cp1251")
    listings = parse_listings(html_text)
    assert len(listings) == 2
    assert listings[0].price_rub == 1520000
    assert listings[0].location == "Владивосток"
    assert listings[1].car_state == ["под заказ"]

    dom_only = """
    <html><body>
      <div data-ftid="bulls-list_bull">
        <div data-ftid="bull_title">
          <a href="https://auto.drom.ru/1.html">Honda Vezel, 2022</a>
        </div>
        <div data-ftid="bull_description-item">1.5 л (132 л.с.)</div>
        <div data-ftid="bull_price">1 620 000 ₽</div>
        <div data-ftid="bull_location">Владивосток</div>
      </div>
      <div data-ftid="bulls-list_bull">
        <div data-ftid="bull_title">
          <a href="https://auto.drom.ru/2.html">Honda Vezel, 2022</a>
        </div>
        <div data-ftid="bull_price">1 100 000 ₽</div>
        <span>под заказ из Японии</span>
      </div>
    </body></html>
    """
    dom_listings = parse_listings(dom_only)
    assert len(dom_listings) == 2
    assert dom_listings[0].price_rub == 1620000
    assert dom_listings[1].car_state == ["под заказ"]


def test_filter_and_aggregate_removes_under_order_and_outliers() -> None:
    listings = [
        DromListing("1", "Corolla", 600000),  # decoy (< 55% of median)
        DromListing("2", "Corolla", 1450000),
        DromListing("3", "Corolla", 1500000),
        DromListing("4", "Corolla", 1520000),
        DromListing("5", "Corolla", 1560000),
        DromListing("6", "Corolla", 1600000),
        DromListing("7", "Corolla", 3900000),  # upper IQR outlier
        DromListing("8", "Corolla", 1200000, description="Привезём под заказ с аукциона"),
        DromListing("9", "Corolla", 1250000, car_state=["в наличии в Китае"]),
        DromListing("10", "Corolla", 1490000, sold=True),
    ]
    stats = filter_and_aggregate(listings)
    assert stats is not None
    assert stats.analogs_count == 5
    assert stats.market_price_rf_rub == 1520000
    assert stats.price_min_rub == 1450000
    assert stats.price_max_rub == 1600000
    assert stats.filtered_out_under_order_count == 5


def test_build_drom_search_url_maps_corolla_touring_and_filters() -> None:
    criteria = DromSearchCriteria(
        make="Toyota",
        model="Corolla Touring",
        year=2020,
        engine_cc=1196,
        drive_type="2WD",
        transmission="6MT",
    )
    url = build_drom_search_url(
        criteria,
        make_slug="toyota",
        model_slug="corolla",
        frame_type_id=3,
        region_scope="dfo",
    )
    assert url.startswith("https://auto.drom.ru/region25/toyota/corolla/bez-probega/?")
    assert "unsold=1" in url
    assert "damaged=2" in url
    assert "whereabouts%5B%5D=0" in url
    assert "minyear=2020" in url
    assert "mv=1.1" in url
    assert "xv=1.3" in url
    assert "frametype%5B%5D=3" in url
    assert "transmission%5B%5D=1" in url


@pytest.mark.django_db
def test_drom_service_cascade_to_all_rf_and_caches_result() -> None:
    calls: list[str] = []
    catalog_model_html = (
        '<html><body><a href="/catalog/toyota/corolla/g_2019_1/">Corolla (NRE210W)</a>'
        "</body></html>"
    )
    catalog_gen_html = (
        "<html><body><table>"
        "<tr><td>1.2 л, 116 л.с., бензин, МКПП, передний привод</td>"
        "<td>Кузов: 3BA-NRE210W</td></tr>"
        "<tr><td>10.2019 - н.в.</td></tr>"
        "</table></body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        calls.append(url)
        if url.endswith("/catalog/toyota/corolla/"):
            return httpx.Response(200, text=catalog_model_html)
        if url.endswith("/catalog/toyota/corolla/g_2019_1/"):
            return httpx.Response(200, text=catalog_gen_html)
        if "region25" in url and "minyear=2020&maxyear=2020" in url:
            return httpx.Response(
                200,
                headers={"Content-Type": "text/html; charset=windows-1251"},
                content=_make_ssr_json_html([_bull(1, 1510000)]),
            )
        if "region25" in url and "minyear=2019&maxyear=2021" in url:
            return httpx.Response(
                200,
                headers={"Content-Type": "text/html; charset=windows-1251"},
                content=_make_ssr_json_html([_bull(1, 1510000), _bull(2, 1550000)]),
            )
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=windows-1251"},
            content=_make_ssr_json_html(
                [_bull(1, 1480000), _bull(2, 1520000), _bull(3, 1580000), _bull(4, 1620000)]
            ),
        )

    client = DromHttpClient(transport=httpx.MockTransport(handler))
    service = DromMarketService(client=client)
    criteria = DromSearchCriteria(
        make="Toyota",
        model="Corolla Touring",
        year=2020,
        engine_cc=1196,
        model_code="3BA-NRE210W",
    )

    result = service.evaluate(criteria)
    market_calls = [u for u in calls if "auto.drom.ru" in u]
    assert len(market_calls) == 3
    assert result.is_fallback is True
    assert result.search_region_ru == "Вся РФ"
    assert result.analogs_count == 4
    assert result.market_price_rf_rub == 1550000
    assert result.power_hp == 116
    assert result.power_hp_source == PowerHpSource.DROM_CATALOG
    assert result.is_under_160_hp is True

    # Second call must hit fresh ExternalCache with zero additional HTTP calls.
    calls.clear()
    cached_result = service.evaluate(criteria)
    assert calls == []
    assert cached_result.market_price_rf_rub == 1550000


@pytest.mark.django_db
def test_drom_slug_api_fallback_on_404() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        calls.append(url)
        if url == "https://auto.drom.ru/toyota/":
            payload = {
                "__slug": "bulls-list-auto",
                "filter": {
                    "models": [
                        {
                            "top": [{"id": 100, "name": "Corolla Rumion"}],
                            "regular": [{"id": 101, "name": "Corolla"}],
                        }
                    ]
                },
            }
            html = (
                "<html><body>"
                '<a href="https://auto.drom.ru/toyota/corolla_rumion/">Corolla Rumion</a>'
                f"<script>{json.dumps(payload)}</script>"
                "</body></html>"
            )
            return httpx.Response(200, text=html)
        if "/toyota/corolla_rumion_x/" in url:
            return httpx.Response(404, text="Not Found")
        if "/toyota/corolla_rumion/" in url:
            return httpx.Response(
                200,
                headers={"Content-Type": "text/html; charset=windows-1251"},
                content=_make_ssr_json_html(
                    [_bull(1, 1100000), _bull(2, 1150000), _bull(3, 1200000)]
                ),
            )
        return httpx.Response(404)

    service = DromMarketService(client=DromHttpClient(transport=httpx.MockTransport(handler)))
    with patch("apps.lots.integrations.drom.slugs._load_drom_schema", return_value={}):
        result = service.evaluate(
            DromSearchCriteria(make="Toyota", model="Corolla Rumion X", year=2015, engine_cc=1496)
        )
    assert result.analogs_count == 3
    assert result.market_price_rf_rub == 1150000
    assert "/toyota/corolla_rumion/" in result.drom_search_url


@pytest.mark.django_db
def test_drom_catalog_power_hp_resolution_and_conservative_max() -> None:
    catalog_model_html = """
    <html><body>
      <a href="/catalog/honda/zr-v/g_2022_14000/">ZR-V 2022 - н.в. (RZ3, RZ4, RZ5, RZ6)</a>
    </body></html>
    """
    catalog_gen_html = """
    <html><body>
      <table>
        <tr>
          <td>1.5 л, 178 л.с., бензин, вариатор, передний привод</td>
          <td>Двигатель: L15C</td>
          <td>Кузов: 5BA-RZ3</td>
        </tr>
        <tr><td>09.2022 - н.в.</td></tr>
        <tr>
          <td>1.5 л, 182 л.с., бензин, вариатор, передний привод</td>
          <td>Двигатель: L15C</td>
          <td>Кузов: 6BA-RZ3</td>
        </tr>
        <tr><td>09.2022 - н.в.</td></tr>
      </table>
    </body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/catalog/honda/zr-v/"):
            return httpx.Response(200, text=catalog_model_html)
        if url.endswith("/catalog/honda/zr-v/g_2022_14000/"):
            return httpx.Response(200, text=catalog_gen_html)
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=windows-1251"},
            content=_make_ssr_json_html([_bull(1, 2900000), _bull(2, 3050000), _bull(3, 3150000)]),
        )

    assert len(parse_catalog_generations(catalog_model_html, model_code="5BA-RZ3")) == 1
    assert len(parse_catalog_power_specs(catalog_gen_html)) == 2

    service = DromMarketService(client=DromHttpClient(transport=httpx.MockTransport(handler)))
    result = service.evaluate(
        DromSearchCriteria(
            make="Honda",
            model="ZR-V",
            year=2023,
            engine_cc=1496,
            fuel_type="gasoline",
            model_code="RZ3",
        )
    )
    assert result.power_hp == 182
    assert result.power_hp_source == PowerHpSource.DROM_CATALOG
    assert result.is_under_160_hp is False


@pytest.mark.django_db
def test_qrator_block_uses_stale_cache_without_retry_spam() -> None:
    market_attempts = 0

    def blocked_handler(request: httpx.Request) -> httpx.Response:
        nonlocal market_attempts
        if "auto.drom.ru" in str(request.url):
            market_attempts += 1
        return httpx.Response(403, text="QRATOR blocked")

    client = DromHttpClient(
        max_retries=2,
        retry_backoff_sec=0.0,
        transport=httpx.MockTransport(blocked_handler),
    )
    service = DromMarketService(client=client)
    criteria = DromSearchCriteria(
        make="Toyota",
        model="Corolla Touring",
        year=2020,
        engine_cc=1196,
        model_code="NRE210",
    )

    # Without cache, raises DromFetchError after single 403 (no retry spam).
    with pytest.raises(DromFetchError):
        service.evaluate(criteria)
    assert market_attempts == 1

    # With stale ExternalCache entry, returns stale cached market result.
    resolved_slug = DromSlugResolver(client).resolve(criteria.make, criteria.model)
    ExternalCache.objects.create(
        key=_build_market_cache_key(criteria, resolved_slug),
        source=ExternalCacheSource.DROM,
        payload={
            "market_price_rf_rub": 1599000,
            "analogs_count": 7,
            "price_min_rub": 1490000,
            "price_max_rub": 1700000,
            "search_region_ru": "ДФО / Владивосток",
            "excludes_under_order": True,
            "filtered_out_under_order_count": 2,
            "is_fallback": False,
            "fallback_reason_ru": None,
            "drom_search_url": "https://auto.drom.ru/region25/toyota/corolla/bez-probega/",
        },
        expires_at=timezone.now() - timedelta(hours=2),
    )
    stale_result = service.evaluate(criteria)
    assert stale_result.market_price_rf_rub == 1599000
    assert stale_result.is_fallback is True
    assert "кэшированные" in (stale_result.fallback_reason_ru or "").lower()


@pytest.mark.django_db
def test_step_drom_market_persists_lot_and_market_info(user_factory) -> None:
    user = user_factory(email="drom_step@example.com")
    batch = Batch.objects.create(user=user)
    lot = Lot.objects.create(
        user=user,
        make="Toyota",
        model="Corolla Touring",
        model_code="3BA-NRE210W",
        year=2020,
        engine_cc=1196,
        drive_type="2WD",
        transmission="6MT",
    )
    item = BatchItem.objects.create(
        batch=batch,
        lot=lot,
        file_index=0,
        original_filename="corolla.jpg",
        status=ItemProcessingStatus.PROCESSING,
        current_step=TaskStep.DROM_MARKET,
    )
    catalog_model_html = (
        '<html><body><a href="/catalog/toyota/corolla/g_2019_1/">Corolla (NRE210W)</a>'
        "</body></html>"
    )
    catalog_gen_html = (
        "<html><body><table>"
        "<tr><td>1.2 л, 116 л.с., бензин, МКПП, передний привод</td>"
        "<td>Кузов: 3BA-NRE210W</td></tr>"
        "<tr><td>10.2019 - н.в.</td></tr>"
        "</table></body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/catalog/toyota/corolla/"):
            return httpx.Response(200, text=catalog_model_html)
        if url.endswith("/catalog/toyota/corolla/g_2019_1/"):
            return httpx.Response(200, text=catalog_gen_html)
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=windows-1251"},
            content=_make_ssr_json_html([_bull(1, 1490000), _bull(2, 1520000), _bull(3, 1580000)]),
        )

    mock_service = DromMarketService(client=DromHttpClient(transport=httpx.MockTransport(handler)))
    with patch("apps.lots.services.DromMarketService", return_value=mock_service):
        ok = _step_drom_market(item)

    assert ok is True
    lot.refresh_from_db()
    assert lot.market_price_rf_rub == 1520000
    assert lot.power_hp == 116
    assert lot.power_hp_source == PowerHpSource.DROM_CATALOG
    assert lot.is_under_160_hp is True

    market_info = MarketComparisonInfo.objects.get(lot=lot)
    assert market_info.analogs_count == 3
    assert market_info.price_min_rub == 1490000
    assert market_info.price_max_rub == 1580000
    assert market_info.is_fallback is False


@pytest.mark.django_db
def test_step_drom_market_marks_item_failed_on_unavailable_model(user_factory) -> None:
    user = user_factory(email="drom_fail@example.com")
    batch = Batch.objects.create(user=user)
    lot = Lot.objects.create(user=user, make="Mitsuoka", model="Orochi", year=2010)
    item = BatchItem.objects.create(
        batch=batch,
        lot=lot,
        file_index=0,
        original_filename="orochi.jpg",
        status=ItemProcessingStatus.PROCESSING,
        current_step=TaskStep.DROM_MARKET,
    )

    def blocked_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="QRATOR blocked")

    mock_service = DromMarketService(
        client=DromHttpClient(max_retries=0, transport=httpx.MockTransport(blocked_handler))
    )
    with patch("apps.lots.services.DromMarketService", return_value=mock_service):
        ok = _step_drom_market(item)

    assert ok is False
    item.refresh_from_db()
    assert item.status == ItemProcessingStatus.FAILED
    assert item.current_step == TaskStep.FAILED
    assert "Drom" in (item.error_message or "")
