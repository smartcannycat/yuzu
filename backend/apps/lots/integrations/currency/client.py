"""HTTP client and payload validation for cbr-xml-daily.ru daily_json.js."""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from apps.lots.integrations.currency.domain import BaseRates, normalize_unit_rate

_REQUIRED_CURRENCIES = ("EUR", "USD", "JPY")


class CbrfFetchError(RuntimeError):
    """Raised when the CBRF source cannot be fetched or fails validation."""


class CbrfClient:
    """Fetches and validates the daily CBRF JSON payload.

    Data source: https://www.cbr-xml-daily.ru/ — a third-party mirror of the
    official Central Bank of Russia daily rates. See the attribution notice in
    docs/API_DATA_CONTRACTS.md (BE-05) for the required backlink.
    """

    def __init__(
        self,
        *,
        api_url: str,
        timeout_sec: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_url = api_url
        self._timeout_sec = timeout_sec
        self._transport = transport

    def fetch_rates(self) -> tuple[BaseRates, datetime]:
        """Fetch the payload and return normalized base rates plus fetch time (UTC)."""
        try:
            response = self._request()
            response.raise_for_status()
            payload = response.json()
        except CbrfFetchError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise CbrfFetchError(f"CBRF request failed: {exc}") from exc
        rates = self._parse_payload(payload)
        return rates, datetime.now(UTC)

    def _request(self) -> httpx.Response:
        with httpx.Client(
            timeout=self._timeout_sec,
            transport=self._transport,
            headers={"Accept": "application/json"},
        ) as client:
            return client.get(self._api_url)

    def _parse_payload(self, payload: Any) -> BaseRates:
        if not isinstance(payload, dict):
            raise CbrfFetchError("CBRF payload is not a JSON object")
        cbrf_date = self._parse_date(payload)
        valutes = payload.get("Valute")
        if not isinstance(valutes, dict):
            raise CbrfFetchError("CBRF payload has no 'Valute' object")
        normalized: dict[str, Decimal] = {}
        for currency in _REQUIRED_CURRENCIES:
            normalized[currency] = self._parse_currency(valutes.get(currency), currency)
        return BaseRates(
            eur_rub=float(normalized["EUR"]),
            usd_rub=float(normalized["USD"]),
            jpy_rub=float(normalized["JPY"]),
            cbrf_date=cbrf_date,
        )

    @staticmethod
    def _parse_date(payload: dict[str, Any]) -> str:
        date_value = payload.get("Date")
        if not isinstance(date_value, str) or not date_value.strip():
            raise CbrfFetchError("CBRF payload has no 'Date' field")
        iso_date = date_value.strip()[:10]
        try:
            datetime.strptime(iso_date, "%Y-%m-%d")
        except ValueError as exc:
            raise CbrfFetchError(f"CBRF payload has an invalid 'Date': {date_value!r}") from exc
        year, month, day = iso_date.split("-")
        return f"{day}.{month}.{year}"

    @staticmethod
    def _parse_currency(raw: Any, currency: str) -> Decimal:
        if not isinstance(raw, dict):
            raise CbrfFetchError(f"CBRF payload is missing the '{currency}' currency")
        try:
            value = Decimal(str(raw["Value"]))
            nominal = Decimal(str(raw["Nominal"]))
        except (KeyError, InvalidOperation, TypeError) as exc:
            raise CbrfFetchError(f"CBRF '{currency}' entry has invalid numeric fields") from exc
        if not value.is_finite() or not nominal.is_finite():
            raise CbrfFetchError(f"CBRF '{currency}' entry has non-finite Value or Nominal")
        if value <= 0 or nominal <= 0:
            raise CbrfFetchError(f"CBRF '{currency}' entry has non-positive Value or Nominal")
        try:
            rate = normalize_unit_rate(value, nominal)
            if rate <= 0:
                raise CbrfFetchError(f"CBRF '{currency}' rate rounds to zero")
            return rate
        except InvalidOperation as exc:
            raise CbrfFetchError(f"CBRF '{currency}' rate cannot be normalized") from exc
