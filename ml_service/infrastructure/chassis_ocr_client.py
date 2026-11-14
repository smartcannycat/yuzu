"""Gemini-based OCR reader for tiny Aleado chassis-number images.

The chassis number on a lot detail page is rendered as a small JPEG
(200x60, dark digits on a light background) in the ``MODEL-CODE-SERIAL``
format (e.g. ``GB5-1025108``). A single Gemini flash call with a strict
JSON schema extracts the characters; results are cached on disk by the
image hash so repeated audits of the same lot do not re-spend quota.
"""

import asyncio
import hashlib
import logging
import re
import time

import httpx
from google.genai import types
from google.genai.errors import ClientError, ServerError

from ml_service.domains.entities import ChassisOcrEntity
from ml_service.infrastructure.gemini_schemas import ChassisRead
from ml_service.infrastructure.gemini_vision_client import AsyncGeminiVisionClient

logger = logging.getLogger(__name__)

# Valid chassis reads: MODEL-CODE-SERIAL (GB5-1025108) or a bare serial
# number. Anything else is passed through as raw for the caller to judge.
_CHASSIS_FORMAT_RE = re.compile(r"^[A-Z0-9]{2,8}-[A-Z0-9]{4,8}$|^\d{4,12}$")
_INTERNAL_SPACE_RE = re.compile(r"\s+")
_CACHE_NAMESPACE = "chassis"


def sanitize_chassis_read(value: str | None) -> tuple[str | None, str | None]:
    """Normalize a raw model output into (frame_id, raw).

    Uppercases, strips and removes internal whitespace. A value matching
    the chassis format (or a bare digit serial) is returned as
    ``frame_id``; anything else is kept only in ``raw``.
    """
    raw = _INTERNAL_SPACE_RE.sub("", (value or "").strip().upper()) or None
    if raw is None:
        return None, None
    if _CHASSIS_FORMAT_RE.fullmatch(raw):
        return raw, raw
    return None, raw


class ChassisOcrClient:
    """Reads chassis numbers from images via one Gemini flash call.

    Reuses the shared key pool semaphore, model failover chain and
    cooldown bookkeeping of :class:`AsyncGeminiVisionClient`; a separate
    disk namespace keeps chassis reads from colliding with sheet caches.
    """

    def __init__(
        self,
        vision_client: AsyncGeminiVisionClient,
        cache_dir,
        request_timeout_seconds: float = 15.0,
    ) -> None:
        self._vision = vision_client
        self._cache_dir = cache_dir
        self._request_timeout_seconds = request_timeout_seconds

    def _cache_path(self, image_bytes: bytes):
        digest = hashlib.sha256(image_bytes).hexdigest()
        return self._cache_dir / f"{_CACHE_NAMESPACE}_{digest}.json"

    async def _read_cached(self, path) -> ChassisOcrEntity | None:
        import json

        if not path.is_file():
            return None
        try:
            payload = await asyncio.to_thread(path.read_text, encoding="utf-8")
            data = json.loads(payload)
            return ChassisOcrEntity(
                frame_id=data.get("frame_id"),
                raw=data.get("raw"),
                confidence=data.get("confidence", "low"),
                cached=True,
                duration_ms=int(data.get("duration_ms", 0)),
            )
        except (OSError, ValueError) as exc:
            logger.warning("Chassis OCR cache read failed: %s", exc)
            return None

    async def _write_cached(self, path, entity: ChassisOcrEntity) -> None:
        import json

        payload = {
            "frame_id": entity.frame_id,
            "raw": entity.raw,
            "confidence": entity.confidence,
            "duration_ms": entity.duration_ms,
        }

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        try:
            await asyncio.to_thread(_write)
        except OSError as exc:
            logger.warning("Chassis OCR cache write failed: %s", exc)

    async def read_chassis_number(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> ChassisOcrEntity:
        """Read the chassis number printed in the image (with disk cache).

        Never raises for transient Gemini failures: an unreadable entity
        with ``frame_id=None`` is returned instead so the caller keeps the
        candidate unverified.
        """
        cache_path = self._cache_path(image_bytes)
        cached = await self._read_cached(cache_path)
        if cached is not None:
            return cached

        t0 = time.perf_counter()
        entity = await self._read_via_gemini(image_bytes, mime_type)
        await self._write_cached(cache_path, entity)
        return entity

    async def _read_via_gemini(self, image_bytes: bytes, mime_type: str) -> ChassisOcrEntity:
        candidates = self._vision._ordered_candidate_models()
        t0 = time.perf_counter()
        last_exc: Exception | None = None

        contents = [
            (
                "Read the vehicle chassis/frame number printed in this image. It looks like "
                "MODEL-CODE-SERIAL, e.g. GB5-1025108. Return exactly the characters you see, "
                "digits and uppercase latin letters, preserving the hyphen. If unreadable, "
                "return null for frame_id."
            ),
            types.Part(
                inline_data=types.Blob(data=image_bytes, mime_type=mime_type),
                media_resolution=types.PartMediaResolution(
                    level=types.PartMediaResolutionLevel.MEDIA_RESOLUTION_LOW
                ),
            ),
        ]
        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
            response_mime_type="application/json",
            response_json_schema=ChassisRead.model_json_schema(),
        )

        for model_name in candidates:
            async with self._vision.key_pool.semaphore:
                api_key = self._vision.key_pool.next_key()
                client = self._vision._get_client(api_key)
                try:
                    response = await asyncio.wait_for(
                        asyncio.to_thread(
                            client.models.generate_content,
                            model=model_name,
                            contents=contents,
                            config=config,
                        ),
                        timeout=self._request_timeout_seconds,
                    )
                except (ClientError, ServerError, TimeoutError, OSError, httpx.HTTPError) as exc:
                    last_exc = exc
                    status_code = getattr(exc, "code", None)
                    if status_code == 429:
                        self._vision.key_pool.mark_key_rate_limited(
                            api_key, self._vision.key_cooldown_seconds
                        )
                    logger.warning("Chassis OCR via %s failed (%s); trying next model.", model_name, exc)
                    self._vision._mark_model_cooldown(model_name, self._vision.model_cooldown_seconds)
                    continue

                if not response.text:
                    last_exc = ValueError(f"Chassis OCR ({model_name}) returned an empty response.")
                    continue

                try:
                    parsed = ChassisRead.model_validate_json(response.text)
                except ValueError as exc:
                    last_exc = exc
                    logger.warning("Chassis OCR via %s returned invalid JSON (%s).", model_name, exc)
                    continue

                frame_id, raw = sanitize_chassis_read(parsed.frame_id)
                return ChassisOcrEntity(
                    frame_id=frame_id,
                    raw=raw or parsed.frame_id,
                    confidence=parsed.confidence,
                    cached=False,
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                )

        logger.warning("Chassis OCR failed on all models; last error: %s", last_exc)
        return ChassisOcrEntity(
            frame_id=None,
            raw=None,
            confidence="low",
            cached=False,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
