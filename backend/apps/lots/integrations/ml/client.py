"""HTTP client for the external ML sheet parsing service."""

import logging
from typing import Any

import httpx

from apps.lots.integrations.ml import schemas

logger = logging.getLogger(__name__)


class MlServiceError(Exception):
    """Raised when the ML service returns an unexpected error response."""


class MlServiceUnavailableError(MlServiceError):
    """Raised when the ML service is unreachable, timed out, or reports 503."""


class MlServiceClient:
    """Synchronous httpx client for the ML sheet parsing API.

    A single instance reuses one ``httpx.Client`` across calls; the pipeline
    creates one parser (and therefore one client) per batch item, and the
    parser closes the client once the item is processed.
    """

    def __init__(
        self,
        *,
        base_url: str,
        timeout_sec: float,
        api_key: str = "",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        headers = {"Accept": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout_sec,
            headers=headers,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def parse_sheet(
        self,
        image_bytes: bytes,
        filename: str,
        *,
        force_refresh: bool = False,
    ) -> schemas.ParserResponse:
        """Upload a sheet image and return the validated parse response.

        Raises:
            ValueError: the ML service rejected the payload with HTTP 400.
            MlServiceUnavailableError: timeout, connection failure, or HTTP 503.
            MlServiceError: any other unexpected HTTP status or invalid payload.
        """
        endpoint = "/api/v1/sheets/parse"
        try:
            response = self._client.post(
                endpoint,
                files={"file": (filename, image_bytes)},
                params={"force_refresh": "true" if force_refresh else "false"},
            )
        except httpx.TimeoutException as exc:
            raise MlServiceUnavailableError(f"ML service timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise MlServiceUnavailableError(f"ML service is unreachable: {exc}") from exc

        if response.status_code == 400:
            raise ValueError(f"ML service rejected the request: {_detail(response)}")
        if response.status_code == 503:
            raise MlServiceUnavailableError(f"ML service is unavailable: {_detail(response)}")
        if response.status_code >= 400:
            raise MlServiceError(
                f"ML service returned HTTP {response.status_code}: {_detail(response)}"
            )

        try:
            return schemas.ParserResponse.model_validate_json(response.content)
        except ValueError as exc:
            logger.warning("ML service returned an invalid payload: %s", exc)
            raise MlServiceError(f"ML service returned an invalid payload: {exc}") from exc


def _detail(response: httpx.Response) -> str:
    try:
        payload: Any = response.json()
    except ValueError:
        return response.text[:200] or "(no body)"
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
    return str(payload)[:200]
