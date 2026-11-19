"""Gemini-based OCR reader for Aleado chassis-number images."""

import asyncio
import hashlib
import logging
import re
import time
from pathlib import Path
from typing import Literal

import httpx
from google.genai import types
from google.genai.errors import ClientError, ServerError
from pydantic import BaseModel, ValidationError

from ml_service.domains.entities import ChassisOcrEntity
from ml_service.infrastructure.atomic_io import atomic_write_json, enforce_cache_limits
from ml_service.infrastructure.gemini_runner import GeminiRunner
from ml_service.infrastructure.gemini_schemas import ChassisRead
from ml_service.infrastructure.gemini_vision_client import AsyncGeminiVisionClient

logger = logging.getLogger(__name__)

# Valid chassis reads: MODEL-CODE-SERIAL (GB5-1025108) or a bare serial
# number. Anything else is passed through as raw for the caller to judge.
_CHASSIS_FORMAT_RE = re.compile(r"^[A-Z0-9]{2,8}-[A-Z0-9]{4,8}$|^\d{4,12}$")
_INTERNAL_SPACE_RE = re.compile(r"\s+")
_CACHE_NAMESPACE = "chassis"


class _CachedChassisRecord(BaseModel):
    frame_id: str | None = None
    raw: str | None = None
    confidence: Literal["high", "medium", "low"] = "low"
    duration_ms: int = 0


def sanitize_chassis_read(value: str | None) -> tuple[str | None, str | None]:
    """Normalize a raw model output into (frame_id, raw)."""
    raw = _INTERNAL_SPACE_RE.sub("", (value or "").strip().upper()) or None
    if raw is None:
        return None, None
    if _CHASSIS_FORMAT_RE.fullmatch(raw):
        return raw, raw
    return None, raw


class ChassisOcrClient:
    """Reads chassis numbers from images via GeminiRunner and bounded disk cache."""

    def __init__(
        self,
        vision_client: AsyncGeminiVisionClient | None = None,
        cache_dir: Path = Path(".cache/sheets"),
        request_timeout_seconds: float = 15.0,
        *,
        runner: GeminiRunner | None = None,
        ttl_seconds: float | None = 604800.0,
        max_disk_bytes: int | None = 512 * 1024 * 1024,
    ) -> None:
        if runner is None:
            if vision_client is None:
                raise ValueError("Either runner or vision_client must be provided.")
            runner = vision_client.runner
        self._runner = runner
        self._cache_dir = Path(cache_dir)
        self._request_timeout_seconds = request_timeout_seconds
        self._ttl_seconds = ttl_seconds
        self._max_disk_bytes = max_disk_bytes

    def _cache_path(self, image_bytes: bytes) -> Path:
        digest = hashlib.sha256(image_bytes).hexdigest()
        return self._cache_dir / f"{_CACHE_NAMESPACE}_{digest}.json"

    def _read_cached_sync(self, path: Path) -> ChassisOcrEntity | None:
        if not path.is_file():
            return None
        try:
            st = path.stat()
            if (
                self._ttl_seconds is not None
                and self._ttl_seconds > 0
                and (time.time() - st.st_mtime) > self._ttl_seconds
            ):
                path.unlink(missing_ok=True)
                return None
            record = _CachedChassisRecord.model_validate_json(path.read_text(encoding="utf-8"))
            return ChassisOcrEntity(
                frame_id=record.frame_id,
                raw=record.raw,
                confidence=record.confidence,
                cached=True,
                duration_ms=record.duration_ms,
            )
        except (OSError, ValueError, TypeError, ValidationError) as exc:
            logger.warning("Chassis OCR cache read failed: %s", exc)
            return None

    async def _read_cached(self, path: Path) -> ChassisOcrEntity | None:
        return await asyncio.to_thread(self._read_cached_sync, path)

    def _write_cached_sync(self, path: Path, payload: dict[str, object]) -> None:
        atomic_write_json(path, payload, prefix=".tmp_chassis_")
        enforce_cache_limits(
            self._cache_dir,
            max_age_seconds=self._ttl_seconds,
            max_bytes=self._max_disk_bytes,
            pattern="*.json",
        )

    async def _write_cached(self, path: Path, entity: ChassisOcrEntity) -> None:
        payload: dict[str, object] = {
            "frame_id": entity.frame_id,
            "raw": entity.raw,
            "confidence": entity.confidence,
            "duration_ms": entity.duration_ms,
        }
        try:
            await asyncio.to_thread(self._write_cached_sync, path, payload)
        except OSError as exc:
            logger.warning("Chassis OCR cache write failed: %s", exc)

    async def read_chassis_number(
        self, image_bytes: bytes, mime_type: str = "image/jpeg"
    ) -> ChassisOcrEntity:
        """Read the chassis number printed in the image (with disk cache)."""
        cache_path = self._cache_path(image_bytes)
        cached = await self._read_cached(cache_path)
        if cached is not None:
            return cached

        entity, should_cache = await self._read_via_gemini(image_bytes, mime_type)
        if should_cache:
            await self._write_cached(cache_path, entity)
        return entity

    def _build_request(
        self, image_bytes: bytes, mime_type: str
    ) -> tuple[list[object], types.GenerateContentConfig]:
        contents: list[object] = [
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
        return contents, config

    async def _try_model(
        self,
        model_name: str,
        contents: list[object],
        config: types.GenerateContentConfig,
        started_at: float,
    ) -> tuple[ChassisOcrEntity | None, bool, Exception | None, bool]:
        """Try one model across healthy keys. Returns (entity, should_cache, exc, abort_all)."""
        key_count = self._runner.key_pool.key_count
        max_tries = max(1, min(key_count, self._runner.max_key_tries)) if key_count > 1 else 1
        last_exc: Exception | None = None

        for _ in range(max_tries):
            async with self._runner.key_pool.acquire() as api_key:
                try:
                    response = await asyncio.wait_for(
                        self._runner.generate_content(
                            api_key=api_key,
                            model_name=model_name,
                            contents=contents,
                            config=config,
                        ),
                        timeout=self._request_timeout_seconds,
                    )
                except ClientError as exc:
                    last_exc = exc
                    status_code = getattr(exc, "code", None)
                    if status_code == 429:
                        self._runner.key_pool.mark_key_rate_limited(
                            api_key, self._runner.key_cooldown_seconds
                        )
                        logger.warning(
                            "Chassis OCR via %s rate-limited (429); trying next healthy key.",
                            model_name,
                        )
                        continue
                    if status_code in (401, 403):
                        logger.warning("Chassis OCR auth/permission error (%s).", status_code)
                        return None, False, exc, True
                    if status_code in (400, 404):
                        logger.warning(
                            "Chassis OCR via %s rejected request (%s); "
                            "skipping model without cooldown.",
                            model_name,
                            status_code,
                        )
                        return None, False, exc, False
                    self._runner.mark_model_cooldown(
                        model_name, self._runner.model_cooldown_seconds
                    )
                    return None, False, exc, False
                except (ServerError, TimeoutError, OSError, httpx.HTTPError) as exc:
                    logger.warning(
                        "Chassis OCR via %s failed (%s); trying next model.", model_name, exc
                    )
                    self._runner.mark_model_cooldown(
                        model_name, self._runner.model_cooldown_seconds
                    )
                    return None, False, exc, False

                if not response.text:
                    return None, False, ValueError(f"Empty chassis OCR from {model_name}."), False

                try:
                    parsed = ChassisRead.model_validate_json(response.text)
                except ValueError as exc:
                    logger.warning("Chassis OCR via %s invalid JSON (%s).", model_name, exc)
                    return None, False, exc, False

                frame_id, raw = sanitize_chassis_read(parsed.frame_id)
                fallback_raw = parsed.frame_id.strip() or None if parsed.frame_id else None
                return (
                    ChassisOcrEntity(
                        frame_id=frame_id,
                        raw=raw or fallback_raw,
                        confidence=parsed.confidence,
                        cached=False,
                        duration_ms=int((time.perf_counter() - started_at) * 1000),
                    ),
                    frame_id is not None,
                    None,
                    False,
                )

        return None, False, last_exc, False

    async def _read_via_gemini(
        self, image_bytes: bytes, mime_type: str
    ) -> tuple[ChassisOcrEntity, bool]:
        candidates = self._runner.ordered_candidate_models()
        t0 = time.perf_counter()
        last_exc: Exception | None = None
        contents, config = self._build_request(image_bytes, mime_type)

        for model_name in candidates:
            entity, should_cache, exc, abort_all = await self._try_model(
                model_name, contents, config, t0
            )
            if entity is not None:
                return entity, should_cache
            if exc is not None:
                last_exc = exc
            if abort_all:
                break

        logger.warning("Chassis OCR failed on all models; last error: %s", last_exc)
        return (
            ChassisOcrEntity(
                frame_id=None,
                raw=None,
                confidence="low",
                cached=False,
                duration_ms=int((time.perf_counter() - t0) * 1000),
            ),
            False,
        )
