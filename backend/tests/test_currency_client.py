"""Unit tests for CBRF payload parsing, normalization and the JPY spread."""

from decimal import Decimal

import httpx
import pytest

from apps.lots.integrations.currency.client import CbrfClient, CbrfFetchError
from apps.lots.integrations.currency.domain import (
    compute_commercial_jpy,
    normalize_unit_rate,
)

API_URL = "https://www.cbr-xml-daily.ru/daily_json.js"


def _payload(**overrides) -> dict:
    base = {
        "Date": "2026-11-12T11:30:00+03:00",
        "Valute": {
            "EUR": {"Value": 95.0, "Nominal": 1},
            "USD": {"Value": 85.0, "Nominal": 1},
            "JPY": {"Value": 58.25, "Nominal": 100},
        },
    }
    base.update(overrides)
    return base


def _client(handler) -> CbrfClient:
    return CbrfClient(api_url=API_URL, transport=httpx.MockTransport(handler))


def _json_handler(payload, status_code: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    return handler


class TestNormalizeUnitRate:
    def test_nominal_normalization(self) -> None:
        # 58.25 rubles per 100 JPY -> 0.5825 per 1 JPY
        assert normalize_unit_rate(Decimal("58.25"), Decimal("100")) == Decimal("0.5825")

    def test_unit_nominal_is_identity(self) -> None:
        assert normalize_unit_rate(Decimal("95.0"), Decimal("1")) == Decimal("95.0000")

    def test_rounds_to_four_places_half_up(self) -> None:
        assert normalize_unit_rate(Decimal("1.00005"), Decimal("1")) == Decimal("1.0001")
        assert normalize_unit_rate(Decimal("0.123456"), Decimal("1")) == Decimal("0.1235")


class TestCommercialJpySpread:
    def test_three_percent_spread(self) -> None:
        assert compute_commercial_jpy(Decimal("0.5825"), Decimal("0.03")) == Decimal("0.6000")

    def test_zero_spred_keeps_rate(self) -> None:
        assert compute_commercial_jpy(Decimal("0.5825"), Decimal("0")) == Decimal("0.5825")


class TestCbrfClientParsing:
    def test_parses_and_normalizes_full_payload(self) -> None:
        client = _client(_json_handler(_payload()))
        rates, fetched_at = client.fetch_rates()
        assert rates.eur_rub == 95.0
        assert rates.usd_rub == 85.0
        assert rates.jpy_rub == 0.5825
        assert rates.cbrf_date == "12.11.2026"
        assert fetched_at is not None

    def test_missing_currency_rejects_payload(self) -> None:
        payload = _payload()
        del payload["Valute"]["JPY"]
        client = _client(_json_handler(payload))
        with pytest.raises(CbrfFetchError, match="JPY"):
            client.fetch_rates()

    @pytest.mark.parametrize(
        "value,nominal",
        [(0, 1), (-95.0, 1), (95.0, 0), (95.0, -1)],
    )
    def test_non_positive_values_reject_payload(self, value, nominal) -> None:
        payload = _payload(Valute={"EUR": {"Value": value, "Nominal": nominal}})
        client = _client(_json_handler(payload))
        with pytest.raises(CbrfFetchError, match="non-positive"):
            client.fetch_rates()

    @pytest.mark.parametrize(
        "eur_entry",
        [
            {"Value": "not-a-number", "Nominal": 1},
            {"Value": None, "Nominal": 1},
            {"Nominal": 1},
            "garbage",
        ],
    )
    def test_non_numeric_fields_reject_payload(self, eur_entry) -> None:
        payload = _payload(Valute={"EUR": eur_entry})
        client = _client(_json_handler(payload))
        with pytest.raises(CbrfFetchError):
            client.fetch_rates()

    def test_missing_date_rejects_payload(self) -> None:
        payload = _payload()
        del payload["Date"]
        client = _client(_json_handler(payload))
        with pytest.raises(CbrfFetchError, match="Date"):
            client.fetch_rates()

    def test_invalid_date_rejects_payload(self) -> None:
        client = _client(_json_handler(_payload(Date="not-a-date")))
        with pytest.raises(CbrfFetchError, match="invalid 'Date'"):
            client.fetch_rates()

    def test_non_object_payload_rejects(self) -> None:
        client = _client(_json_handler([1, 2, 3]))
        with pytest.raises(CbrfFetchError):
            client.fetch_rates()

    def test_http_error_raises_fetch_error(self) -> None:
        client = _client(_json_handler({}, status_code=500))
        with pytest.raises(CbrfFetchError):
            client.fetch_rates()

    def test_invalid_json_raises_fetch_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="not json at all")

        client = _client(handler)
        with pytest.raises(CbrfFetchError):
            client.fetch_rates()

    def test_transport_timeout_raises_fetch_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("timed out")

        client = _client(handler)
        with pytest.raises(CbrfFetchError, match="CBRF request failed"):
            client.fetch_rates()


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "1e1000"])
@pytest.mark.parametrize("field", ["Value", "Nominal"])
def test_invalid_numeric_quotes_use_fetch_error(value, field) -> None:
    payload = _payload()
    payload["Valute"]["JPY"][field] = value
    client = _client(_json_handler(payload))
    with pytest.raises(CbrfFetchError):
        client.fetch_rates()


@pytest.mark.parametrize("status", [301, 404, 429, 500, 503])
def test_unsuccessful_status_rejected_even_with_valid_rates(status) -> None:
    client = _client(_json_handler(_payload(), status_code=status))
    with pytest.raises(CbrfFetchError):
        client.fetch_rates()


def test_rate_rounding_to_zero_is_rejected() -> None:
    payload = _payload()
    payload["Valute"]["JPY"] = {"Value": 0.00000001, "Nominal": 100}
    with pytest.raises(CbrfFetchError):
        _client(_json_handler(payload)).fetch_rates()
