"""HTTP client for the external ML sheet parsing service."""

from __future__ import annotations

import json
import logging
import mimetypes
from pathlib import Path
from typing import Any

import httpx

from apps.integrations.ml import schemas

logger = logging.getLogger(__name__)

_EXT_MIME_MAP: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}
_HEIC_BRANDS = frozenset({b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"})


class MlServiceError(Exception):
    """Raised when the ML service returns an unexpected error response."""


class MlServiceUnavailableError(MlServiceError):
    """Raised when the ML service is unreachable, timed out, rate-limited, or reports 503."""


def _guess_image_mime(image_bytes: bytes, filename: str) -> str:
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(image_bytes) >= 12 and image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    if len(image_bytes) >= 12 and image_bytes[4:8] == b"ftyp" and image_bytes[8:12] in _HEIC_BRANDS:
        return "image/heif" if image_bytes[8:12] == b"mif1" else "image/heic"

    ext = Path(filename or "").suffix.lower()
    if ext in _EXT_MIME_MAP:
        return _EXT_MIME_MAP[ext]
    guessed, _ = mimetypes.guess_type(filename or "")
    return guessed or "application/octet-stream"


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

    def __enter__(self) -> MlServiceClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _post_image(
        self,
        endpoint: str,
        *,
        filename: str,
        image_bytes: bytes,
        mime_type: str,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            response = self._client.post(
                endpoint,
                files={"file": (filename, image_bytes, mime_type)},
                params=params,
            )
        except httpx.TimeoutException as exc:
            raise MlServiceUnavailableError(f"ML service timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise MlServiceUnavailableError(f"ML service is unreachable: {exc}") from exc

        if response.status_code == 400:
            raise ValueError(f"ML service rejected the request: {_detail(response)}")
        if response.status_code in {429, 503}:
            raise MlServiceUnavailableError(f"ML service is unavailable: {_detail(response)}")
        if response.status_code >= 400:
            raise MlServiceError(
                f"ML service returned HTTP {response.status_code}: {_detail(response)}"
            )
        return response

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
            MlServiceUnavailableError: timeout, connection failure, HTTP 429, or HTTP 503.
            MlServiceError: any other unexpected HTTP status or invalid payload.
        """
        response = self._post_image(
            "/api/v1/sheets/parse",
            filename=filename,
            image_bytes=image_bytes,
            mime_type=_guess_image_mime(image_bytes, filename),
            params={"force_refresh": "true" if force_refresh else "false"},
        )
        try:
            return schemas.ParserResponse.model_validate_json(response.content)
        except ValueError as exc:
            logger.warning("ML service returned an invalid payload: %s", exc)
            raise MlServiceError(f"ML service returned an invalid payload: {exc}") from exc

    def read_chassis(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
    ) -> schemas.ChassisRead | None:
        """Read the chassis number from a chassis-number image via the ML service.

        Returns ``None`` when the model could not read the image or returns JSON ``null``.

        Raises:
            ValueError: the ML service rejected the payload with HTTP 400.
            MlServiceUnavailableError: timeout, connection failure, HTTP 429, or HTTP 503.
            MlServiceError: any other unexpected HTTP status or invalid payload.
        """
        filename = "chassis.png" if mime_type == "image/png" else "chassis.jpg"
        response = self._post_image(
            "/api/v1/chassis/read",
            filename=filename,
            image_bytes=image_bytes,
            mime_type=mime_type,
        )
        try:
            parsed: Any = json.loads(response.content)
        except ValueError as exc:
            logger.warning("ML service returned an invalid chassis payload: %s", exc)
            raise MlServiceError(f"ML service returned an invalid payload: {exc}") from exc
        if parsed is None:
            return None
        try:
            return schemas.ChassisRead.model_validate(parsed)
        except ValueError as exc:
            logger.warning("ML service returned an invalid chassis payload: %s", exc)
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
