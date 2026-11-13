"""Integration tests for the currency rates service cache and fallback chain."""

from datetime import timedelta
from decimal import Decimal

import httpx
import pytest
from django.utils import timezone

from apps.core.models import ExternalCache
from apps.lots.integrations.currency.cache import CACHE_KEY, CurrencyCache
from apps.lots.integrations.currency.client import CbrfClient
from apps.lots.integrations.currency.domain import (
    BaseRates,
    RatesOrigin,
)
from apps.lots.integrations.currency.service import (
    CurrencyRatesService,
)

API_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
TTL = timedelta(seconds=3600)
SPREAD = Decimal("0.03")

FALLBACK = BaseRates(
    eur_rub=90.0,
    usd_rub=80.0,
    jpy_rub=0.5,
    cbrf_date="01.01.2026",
)

LIVE_RATES = BaseRates(eur_rub=95.0, usd_rub=85.0, jpy_rub=0.5825, cbrf_date="12.11.2026")
OTHER_RATES = BaseRates(eur_rub=96.0, usd_rub=86.0, jpy_rub=0.59, cbrf_date="13.11.2026")


def _ok_handler(payload=None):
    body = payload or {
        "Date": "2026-11-12T11:30:00+03:00",
        "Valute": {
            "EUR": {"Value": 95.0, "Nominal": 1},
            "USD": {"Value": 85.0, "Nominal": 1},
            "JPY": {"Value": 58.25, "Nominal": 100},
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    return handler


def _fail_handler():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("source down")

    return handler


def _service(handler, *, cache: CurrencyCache | None = None) -> tuple[CurrencyRatesService, list]:
    calls: list[httpx.Request] = []

    def counting(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return handler(request)

    client = CbrfClient(
        api_url=API_URL,
        transport=httpx.MockTransport(counting),
    )
    service = CurrencyRatesService(
        client=client,
        cache=cache or CurrencyCache(),
        fallback_config=FALLBACK,
        spread=SPREAD,
        ttl=TTL,
    )
    return service, calls


def _write_cache(
    rates: BaseRates = LIVE_RATES,
    *,
    fetched_at=None,
    expires_at=None,
    updated_at=None,
) -> None:
    cache = CurrencyCache()
    moment = fetched_at or timezone.now()
    cache.write(rates, moment, ttl=TTL)
    if expires_at is not None or updated_at is not None:
        # auto_now would override a hand-set updated_at on save(), so patch via queryset.
        entry = ExternalCache.objects.get(key=CACHE_KEY)
        if expires_at is not None:
            ExternalCache.objects.filter(pk=entry.pk).update(expires_at=expires_at)
        if updated_at is not None:
            ExternalCache.objects.filter(pk=entry.pk).update(updated_at=updated_at)


@pytest.mark.django_db
class TestFreshCache:
    def test_fresh_cache_answers_without_http(self) -> None:
        _write_cache()
        service, calls = _service(_fail_handler())
        result = service.get_currency_rates()
        assert result.origin == RatesOrigin.CACHE
        assert result.eur_rub == 95.0
        assert result.cbrf_date == "12.11.2026"
        assert result.is_fallback is False
        assert calls == []

    def test_expired_cache_triggers_live_fetch(self) -> None:
        _write_cache(expires_at=timezone.now() - timedelta(seconds=1))
        service, calls = _service(_ok_handler())
        result = service.get_currency_rates()
        assert result.origin == RatesOrigin.LIVE
        assert len(calls) == 1

    def test_weekend_keeps_source_date(self) -> None:
        # Saturday source date must survive the round trip through the cache.
        weekend = BaseRates(eur_rub=95.0, usd_rub=85.0, jpy_rub=0.5825, cbrf_date="14.11.2026")
        _write_cache(weekend)
        service, _calls = _service(_fail_handler())
        result = service.get_currency_rates()
        assert result.cbrf_date == "14.11.2026"


@pytest.mark.django_db
class TestLiveFetch:
    def test_live_fetch_writes_cache_and_applies_spread(self) -> None:
        service, calls = _service(_ok_handler())
        result = service.get_currency_rates()
        assert result.origin == RatesOrigin.LIVE
        assert len(calls) == 1
        assert result.jpy_rub == pytest.approx(0.5825)
        assert result.commercial_jpy_rub == pytest.approx(0.6, abs=1e-4)
        assert result.jpy_rate_source == "Расчётный ориентир: ЦБ РФ + 3%"

    def test_second_call_uses_cache_no_second_http(self) -> None:
        service, calls = _service(_ok_handler())
        service.get_currency_rates()
        assert len(calls) == 1
        result = service.get_currency_rates()
        assert result.origin == RatesOrigin.CACHE
        assert len(calls) == 1
