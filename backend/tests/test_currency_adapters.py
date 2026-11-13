"""Tests for schema adapters, settings wiring and the management command."""

import datetime as dt
from decimal import Decimal
from unittest.mock import patch

import httpx
import pytest
from django.core.management import call_command

from apps.lots.integrations.currency.cache import CurrencyCache
from apps.lots.integrations.currency.client import CbrfClient
from apps.lots.integrations.currency.domain import (
    BaseRates,
    CurrencyRatesResult,
    RatesOrigin,
)
from apps.lots.integrations.currency.service import (
    build_currency_service,
    to_currency_rates_schema,
    to_customs_rates_input,
)
from config.settings.config import AppSettings


def _result(origin: RatesOrigin = RatesOrigin.LIVE) -> CurrencyRatesResult:
    return CurrencyRatesResult(
        base=BaseRates(eur_rub=95.0, usd_rub=85.0, jpy_rub=0.5825, cbrf_date="12.11.2026"),
        commercial_jpy_rub=0.6,
        jpy_rate_source="Расчётный ориентир: ЦБ РФ + 3%",
        origin=origin,
        fetched_at=dt.datetime.now(tz=dt.UTC),
        is_fallback=False,
    )


class TestAdapters:
    def test_to_currency_rates_schema_keeps_public_format(self) -> None:
        schema = to_currency_rates_schema(_result())
        assert schema.jpy_rub_bank == 0.6
        assert schema.eur_rub_cbrf == 95.0
        assert schema.usd_rub_cbrf == 85.0
        assert schema.cbrf_date == "12.11.2026"
        assert schema.jpy_rate_source == "Расчётный ориентир: ЦБ РФ + 3%"
        # Numbers stay numbers and the date stays DD.MM.YYYY.
        assert isinstance(schema.jpy_rub_bank, float)
        assert isinstance(schema.eur_rub_cbrf, float)

    def test_to_customs_rates_input_round_trips(self) -> None:
        payload = to_customs_rates_input(_result())
        assert payload["jpy_rub_bank"] == 0.6
        assert payload["cbrf_date"] == "12.11.2026"

    def test_schema_is_strict(self) -> None:
        from pydantic import ValidationError

        from apps.lots.schemas import CurrencyRates

        with pytest.raises(ValidationError):
            CurrencyRates.model_validate({"jpy_rub_bank": 0.6})


class TestSettings:
    def test_fallback_rates_parse_from_json_string(self) -> None:
        raw = '{"eur_rub": 95, "usd_rub": 85, "jpy_rub": 0.58, "cbrf_date": "01.01.2026"}'
        settings = AppSettings(_env_file=None, CBRF_FALLBACK_RATES=raw)
        assert settings.CBRF_FALLBACK_RATES["jpy_rub"] == 0.58

    def test_invalid_fallback_json_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AppSettings(_env_file=None, CBRF_FALLBACK_RATES="not-json")

    def test_production_requires_fallback_rates(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="CBRF_FALLBACK_RATES"):
            AppSettings(
                _env_file=None,
                ENVIRONMENT="production",
                DEBUG=False,
                SECRET_KEY="x" * 40,
                ALLOWED_HOSTS=["api.yuzu.ru"],
            )

    def test_default_spread_is_three_percent(self) -> None:
        settings = AppSettings(_env_file=None)
        assert settings.CBRF_JPY_SPREAD == 0.03


class TestFactory:
    def test_build_service_uses_local_defaults_when_unset(self) -> None:
        service = build_currency_service()
        assert service is not None

    def test_build_service_injects_transport(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("must not be called during construction")

        service = build_currency_service(transport=httpx.MockTransport(handler))
        assert service is not None


@pytest.mark.django_db
class TestManagementCommand:
    def test_refresh_currency_rates_warms_cache(self, capsys) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "Date": "2026-11-12T11:30:00+03:00",
                    "Valute": {
                        "EUR": {"Value": 95.0, "Nominal": 1},
                        "USD": {"Value": 85.0, "Nominal": 1},
                        "JPY": {"Value": 58.25, "Nominal": 100},
                    },
                },
            )

        with patch(
            "apps.lots.management.commands.refresh_currency_rates.build_currency_service",
            return_value=build_currency_service(transport=httpx.MockTransport(handler)),
        ):
            call_command("refresh_currency_rates")
            out = capsys.readouterr().out
            assert "origin=live" in out
            assert "cbrf_date=12.11.2026" in out
            cache = CurrencyCache()
            assert cache.read_fresh() is not None


@pytest.mark.django_db
class TestAdvisoryLockContention:
    def test_lock_holder_updates_and_others_fall_back(self, monkeypatch) -> None:
        """Simulate two processes: the first holds the advisory lock, the second
        must not issue an HTTP request and must use the stale/config path."""
        from apps.lots.integrations.currency.service import CurrencyRatesService

        cache = CurrencyCache()
        # Pre-seed a stale-but-valid set.
        cache.write(
            BaseRates(eur_rub=94.0, usd_rub=84.0, jpy_rub=0.57, cbrf_date="10.11.2026"),
            dt.datetime.now(tz=dt.UTC) - dt.timedelta(seconds=7200),
            ttl=dt.timedelta(seconds=3600),
        )
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return httpx.Response(200, json={})

        client = CbrfClient(
            api_url="https://example.invalid",
            transport=httpx.MockTransport(handler),
        )

        # Second process: the lock is already taken by "someone else".
        def locked_acquire() -> bool:
            return False

        contender = CurrencyRatesService(
            client=client,
            cache=cache,
            fallback_config=BaseRates(
                eur_rub=90.0, usd_rub=80.0, jpy_rub=0.5, cbrf_date="01.01.2026"
            ),
            spread=Decimal("0.03"),
            ttl=dt.timedelta(seconds=3600),
        )
        monkeypatch.setattr(contender, "_try_acquire_updater_lock", locked_acquire)
        result = contender.get_currency_rates()
        assert calls == []
        assert result.origin == RatesOrigin.STALE
        assert result.fallback_reason == "another process is updating rates"
