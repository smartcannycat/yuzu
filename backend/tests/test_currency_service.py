"""Integration tests for the currency rates service cache and fallback chain."""

from datetime import timedelta
from decimal import Decimal

import httpx
import pytest
from django.utils import timezone

from apps.core.enums import ExternalCacheSource
from apps.core.models import ExternalCache
from apps.lots.integrations.currency.cache import CACHE_KEY, LOCK_KEY, PAUSE_KEY, CurrencyCache
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


@pytest.mark.django_db
class TestSourceFailure:
    def test_failure_falls_back_to_stale_db_set(self) -> None:
        _write_cache(expires_at=timezone.now() - timedelta(seconds=1))
        service, _calls = _service(_fail_handler())
        result = service.get_currency_rates()
        assert result.origin == RatesOrigin.STALE
        assert result.is_fallback is True
        assert result.fallback_reason is not None
        assert result.eur_rub == 95.0

    def test_failure_writes_pause_marker(self) -> None:
        service, _ = _service(_fail_handler())
        service.get_currency_rates()
        assert ExternalCache.objects.filter(key=PAUSE_KEY).exists()

    def test_pause_prevents_http_on_next_call(self) -> None:
        _write_cache(expires_at=timezone.now() - timedelta(seconds=1))
        service, calls = _service(_fail_handler())
        service.get_currency_rates()
        assert len(calls) == 1
        # Next call: source still down, but the pause must skip the HTTP attempt.
        service2, calls2 = _service(_fail_handler())
        service2.get_currency_rates()
        assert calls2 == []

    def test_pause_expires_after_60_seconds(self) -> None:
        cache = CurrencyCache()
        cache.mark_pause(now=timezone.now() - timedelta(seconds=61))
        service, calls = _service(_ok_handler())
        result = service.get_currency_rates()
        assert result.origin == RatesOrigin.LIVE
        assert len(calls) == 1

    def test_stale_set_older_than_seven_days_is_ignored(self) -> None:
        _write_cache(
            expires_at=timezone.now() - timedelta(seconds=1),
            fetched_at=timezone.now() - timedelta(days=8),
        )
        service, _ = _service(_fail_handler())
        result = service.get_currency_rates()
        assert result.origin == RatesOrigin.CONFIG
        assert result.eur_rub == 90.0
        assert result.cbrf_date == "01.01.2026"

    def test_config_fallback_marks_reason(self) -> None:
        service, _ = _service(_fail_handler())
        result = service.get_currency_rates()
        assert result.origin == RatesOrigin.CONFIG
        assert result.is_fallback is True
        assert result.fallback_reason is not None

    def test_active_pause_returns_config_without_http(self) -> None:
        cache = CurrencyCache()
        cache.mark_pause()
        service, calls = _service(_ok_handler(), cache=cache)
        result = service.get_currency_rates()
        assert result.origin == RatesOrigin.CONFIG
        assert calls == []
        assert cache.is_paused()

    def test_refresh_bypasses_pause_and_cache(self) -> None:
        _write_cache()
        cache = CurrencyCache()
        cache.mark_pause()
        service, calls = _service(_ok_handler(), cache=cache)
        result = service.refresh()
        assert result.origin == RatesOrigin.LIVE
        assert len(calls) == 1
        assert not ExternalCache.objects.filter(key=PAUSE_KEY).exists()

    def test_refresh_failure_returns_stale(self) -> None:
        _write_cache(expires_at=timezone.now() - timedelta(seconds=1))
        service, _ = _service(_fail_handler())
        result = service.refresh()
        assert result.origin == RatesOrigin.STALE


@pytest.mark.django_db
class TestCacheIntegrity:
    def test_corrupted_cache_payload_is_ignored(self) -> None:
        ExternalCache.objects.create(
            key=CACHE_KEY,
            source=ExternalCacheSource.CBRF,
            payload={"garbage": True},
            expires_at=timezone.now() + TTL,
        )
        service, calls = _service(_ok_handler())
        result = service.get_currency_rates()
        assert result.origin == RatesOrigin.LIVE
        assert len(calls) == 1

    def test_non_positive_cached_rates_are_ignored(self) -> None:
        ExternalCache.objects.create(
            key=CACHE_KEY,
            source=ExternalCacheSource.CBRF,
            payload={
                "eur_rub": "-95.0",
                "usd_rub": "85.0",
                "jpy_rub": "0.5825",
                "cbrf_date": "12.11.2026",
                "fetched_at": timezone.now().isoformat(),
            },
            expires_at=timezone.now() + TTL,
        )
        service, _ = _service(_fail_handler())
        result = service.get_currency_rates()
        assert result.origin == RatesOrigin.CONFIG

    def test_failed_update_keeps_last_valid_set(self) -> None:
        _write_cache(LIVE_RATES)
        # Fresh cache -> no HTTP at all; verify the entry survives a failed
        # refresh attempt without being overwritten.
        cache = CurrencyCache()
        service, _ = _service(_fail_handler(), cache=cache)
        service.refresh()
        entry = ExternalCache.objects.get(key=CACHE_KEY)
        assert entry.payload["eur_rub"] == "95.0"

    def test_successful_update_is_atomic_single_entry(self) -> None:
        _write_cache(LIVE_RATES)
        service, _ = _service(_ok_handler())
        service.refresh()
        assert ExternalCache.objects.filter(key=CACHE_KEY).count() == 1
        entry = ExternalCache.objects.get(key=CACHE_KEY)
        assert entry.source == ExternalCacheSource.CBRF
        assert entry.payload["eur_rub"] == "95.0"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field,value",
    [
        ("eur_rub", "NaN"),
        ("usd_rub", "Infinity"),
        ("jpy_rub", "1e1000"),
        ("cbrf_date", "31.02.2026"),
        ("fetched_at", "2026-01-01T00:00:00"),
    ],
)
def test_invalid_cached_values_are_ignored(field, value) -> None:
    _write_cache()
    entry = ExternalCache.objects.get(key=CACHE_KEY)
    payload = {**entry.payload, field: value}
    ExternalCache.objects.filter(pk=CACHE_KEY).update(payload=payload)
    service, calls = _service(_fail_handler())
    result = service.get_currency_rates()
    assert result.origin == RatesOrigin.CONFIG
    assert len(calls) == 1


@pytest.mark.django_db
@pytest.mark.parametrize("updated_by_peer", ["cache", "pause"])
def test_rechecks_cache_and_pause_after_acquiring_lock(monkeypatch, updated_by_peer) -> None:
    service, calls = _service(_ok_handler())
    acquire = service._try_acquire_updater_lock

    def acquire_after_peer_update():
        if updated_by_peer == "cache":
            _write_cache(OTHER_RATES)
        else:
            CurrencyCache().mark_pause()
        return acquire()

    monkeypatch.setattr(service, "_try_acquire_updater_lock", acquire_after_peer_update)
    result = service.get_currency_rates()
    assert result.origin == (
        RatesOrigin.CACHE if updated_by_peer == "cache" else RatesOrigin.CONFIG
    )
    assert calls == []


@pytest.mark.django_db
def test_failed_manual_refresh_sets_pause() -> None:
    service, calls = _service(_fail_handler())
    service.refresh()
    assert CurrencyCache().is_paused()
    service.get_currency_rates()
    assert len(calls) == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("force", [False, True])
def test_postgres_lock_serializes_updates_across_connections(force) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from django.db import connections

    started, finish = Event(), Event()

    def slow_handler(request):
        started.set()
        assert finish.wait(timeout=10), "Test did not release the source request"
        return _ok_handler()(request)

    def update_in_other_connection():
        try:
            service, _ = _service(slow_handler)
            return service.get_currency_rates()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        updater = pool.submit(update_in_other_connection)
        try:
            assert started.wait(timeout=10), "Updater did not reach the source"
            contender, calls = _service(_ok_handler())
            result = contender.refresh() if force else contender.get_currency_rates()
            assert result.origin == RatesOrigin.CONFIG
            assert calls == []
        finally:
            finish.set()
        assert updater.result(timeout=10).origin == RatesOrigin.LIVE
    # The updater lease was released and the contender can refresh.
    assert contender.refresh().origin == RatesOrigin.LIVE
    assert len(calls) == 1


@pytest.mark.django_db(transaction=True)
def test_http_fetch_runs_without_open_db_transaction() -> None:
    from django.db import connection

    observed: dict[str, object] = {}

    def inspecting_handler(request: httpx.Request) -> httpx.Response:
        observed["in_atomic_block"] = connection.in_atomic_block
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM pg_locks "
                    "WHERE locktype = 'advisory' AND pid = pg_backend_pid()"
                )
                observed["advisory_locks"] = cursor.fetchone()[0]
                cursor.execute("SELECT pg_current_xact_id_if_assigned() IS NOT NULL")
                observed["has_assigned_xact_id"] = cursor.fetchone()[0]
        return _ok_handler()(request)

    service, _ = _service(inspecting_handler)
    result = service.get_currency_rates()
    assert result.origin == RatesOrigin.LIVE
    assert observed["in_atomic_block"] is False
    if connection.vendor == "postgresql":
        assert observed["advisory_locks"] == 0
        assert observed["has_assigned_xact_id"] is False
    assert not ExternalCache.objects.filter(key=LOCK_KEY).exists()


@pytest.mark.django_db
def test_lease_is_released_on_unexpected_error() -> None:
    def broken_handler(request: httpx.Request) -> httpx.Response:
        raise RuntimeError("boom")

    service, _ = _service(broken_handler)
    with pytest.raises(RuntimeError, match="boom"):
        service.get_currency_rates()
    assert not ExternalCache.objects.filter(key=LOCK_KEY).exists()

    ok_service, _ = _service(_ok_handler())
    assert ok_service.refresh().origin == RatesOrigin.LIVE


@pytest.mark.django_db
def test_expired_lease_can_be_reclaimed_and_stale_owner_cannot_release_it() -> None:
    cache = CurrencyCache()
    now = timezone.now()
    assert cache.try_acquire_lock(
        "dead-worker", ttl=timedelta(seconds=5), now=now - timedelta(seconds=10)
    )
    assert not cache.try_acquire_lock(
        "too-early", ttl=timedelta(seconds=5), now=now - timedelta(seconds=7)
    )
    assert cache.try_acquire_lock("new-worker", ttl=timedelta(seconds=30), now=now)

    # Stale owner releasing late must not evict the active owner's lease.
    cache.release_lock("dead-worker")
    assert not cache.try_acquire_lock("contender", ttl=timedelta(seconds=30), now=now)

    cache.release_lock("new-worker")
    assert cache.try_acquire_lock("contender", ttl=timedelta(seconds=30), now=now)
