import asyncio
import base64
import logging
import time
from dataclasses import replace

import httpx
from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError

from ml_service.domains.entities import (
    FastHeaderPreviewEntity,
    GatekeeperDecisionEntity,
    ModelAttemptEntity,
    RawExtractionEntity,
    SlicedSheetEntity,
)
from ml_service.domains.enums import LayoutComplexity
from ml_service.infrastructure.gemini_schemas import (
    SYSTEM_PROMPT,
    AuctionExtractionSchema,
    FastHeaderPreviewSchema,
    to_raw_extraction_entity,
)
from ml_service.infrastructure.image_formats import detect_mime_from_magic_bytes
from ml_service.infrastructure.key_pool import GeminiKeyPool

logger = logging.getLogger(__name__)

_THINKING_LEVELS: dict[str, types.ThinkingLevel] = {
    "MINIMAL": types.ThinkingLevel.MINIMAL,
    "LOW": types.ThinkingLevel.LOW,
    "MEDIUM": types.ThinkingLevel.MEDIUM,
    "HIGH": types.ThinkingLevel.HIGH,
}


def _resolve_thinking_level(level_name: str) -> types.ThinkingLevel:
    """Resolve configured thinking level name to SDK ThinkingLevel enum."""
    return _THINKING_LEVELS.get(level_name.strip().upper(), types.ThinkingLevel.LOW)


def _image_part(
    image_bytes: bytes,
    level: types.PartMediaResolutionLevel,
    mime_type: str = "image/png",
) -> types.Part:
    """Build an image Part with per-part Gemini 3 media resolution."""
    return types.Part(
        inline_data=types.Blob(data=image_bytes, mime_type=mime_type),
        media_resolution=types.PartMediaResolution(level=level),
    )


def _build_extraction_contents(
    sliced: SlicedSheetEntity,
    complexity: LayoutComplexity,
) -> list[str | types.Part]:
    """Assemble prompt text and per-part image payloads based on sheet complexity."""
    mime_type = sliced.mime_type or detect_mime_from_magic_bytes(sliced.full_png)
    if complexity == LayoutComplexity.CLEAN_DIGITAL:
        return [
            "Лист аукциона:",
            _image_part(sliced.full_png, types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH, mime_type),
            "Извлеки данные строго по JSON-схеме.",
        ]

    return [
        "Общий лист (для ориентации сторон и общей структуры):",
        _image_part(sliced.full_png, types.PartMediaResolutionLevel.MEDIA_RESOLUTION_LOW, mime_type),
        "Фрагмент 1 (верх-лево):",
        _image_part(sliced.crops_png["top_left"], types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH, mime_type),
        "Фрагмент 2 (верх-право — оценки, чек-лист опций, продавец):",
        _image_part(sliced.crops_png["top_right"], types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH, mime_type),
        "Фрагмент 3 (низ-лево — заметки инспектора, шасси):",
        _image_part(sliced.crops_png["bottom_left"], types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH, mime_type),
        "Фрагмент 4 (низ-право — схема дефектов, вертикальный текст):",
        _image_part(sliced.crops_png["bottom_right"], types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH, mime_type),
        "Извлеки данные строго по JSON-схеме. Не дублируй метки с пересечений фрагментов.",
    ]


class AsyncGeminiVisionClient:
    """Async wrapper around google-genai SDK with model failover, cooldown, and cached clients."""

    def __init__(
        self,
        key_pool: GeminiKeyPool,
        decision_model: str = "gemini-decision-1",
        flash_model: str = "gemini-3.6-flash",
        fallback_models: list[str] | None = None,
        enable_gatekeeper: bool = True,
        gatekeeper_fail_open: bool = True,
        request_timeout_ms: int = 25000,
        sdk_max_attempts: int = 1,
        model_cooldown_seconds: float = 120.0,
        key_cooldown_seconds: float = 30.0,
        thinking_level: str = "LOW",
        request_deadline_seconds: float = 45.0,
        hedge_delay_seconds: float = 8.0,
        fast_header_timeout_seconds: float = 1.2,
        gatekeeper_sheet_threshold: float = 0.60,
        gatekeeper_readable_threshold: float = 0.50,
        client_error_cooldown_seconds: float = 300.0,
        max_key_tries: int = 3,
    ) -> None:
        self.key_pool = key_pool
        self.decision_model = decision_model
        self.flash_model = flash_model
        self.enable_gatekeeper = enable_gatekeeper
        self.gatekeeper_fail_open = gatekeeper_fail_open
        self.request_timeout_ms = request_timeout_ms
        self.sdk_max_attempts = sdk_max_attempts
        self.model_cooldown_seconds = model_cooldown_seconds
        self.key_cooldown_seconds = key_cooldown_seconds
        self.thinking_level = thinking_level
        self.request_deadline_seconds = request_deadline_seconds
        self.hedge_delay_seconds = hedge_delay_seconds
        self.fast_header_timeout_seconds = fast_header_timeout_seconds
        self.gatekeeper_sheet_threshold = gatekeeper_sheet_threshold
        self.gatekeeper_readable_threshold = gatekeeper_readable_threshold
        self.client_error_cooldown_seconds = client_error_cooldown_seconds
        self.max_key_tries = max_key_tries

        chain = [flash_model, *(fallback_models or [])]
        seen: set[str] = set()
        self._model_chain: list[str] = []
        for model_name in chain:
            cleaned = model_name.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                self._model_chain.append(cleaned)

        self._model_cooldown_until: dict[str, float] = {}
        self._clients: dict[str, genai.Client] = {}

    @property
    def flash_model_name(self) -> str:
        """Return primary configured Vision extraction model name."""
        return self.flash_model

    def _get_client(self, api_key: str) -> genai.Client:
        """Return cached genai.Client per API key with explicit timeout and retry caps."""
        client = self._clients.get(api_key)
        if client is None:
            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(
                    api_version="v1beta",
                    timeout=self.request_timeout_ms,
                    retry_options=types.HttpRetryOptions(attempts=self.sdk_max_attempts),
                ),
            )
            self._clients[api_key] = client
        return client

    def _ordered_candidate_models(self) -> list[str]:
        """Return healthy models first in priority order, then cooled-down models by earliest expiry."""
        now = time.monotonic()
        healthy: list[str] = []
        cooled: list[tuple[float, str]] = []
        for model_name in self._model_chain:
            until = self._model_cooldown_until.get(model_name, 0.0)
            if until <= now:
                healthy.append(model_name)
            else:
                cooled.append((until, model_name))
        cooled.sort(key=lambda item: item[0])
        return [*healthy, *(name for _, name in cooled)]

    def _mark_model_cooldown(self, model_name: str, duration_seconds: float) -> None:
        if duration_seconds > 0:
            self._model_cooldown_until[model_name] = time.monotonic() + duration_seconds

    async def check_sheet(self, full_png: bytes, mime_type: str | None = None) -> GatekeeperDecisionEntity:
        """Run fast gatekeeper classification via Gemini Decisions API with optional fail-open."""
        if not self.enable_gatekeeper:
            return GatekeeperDecisionEntity(
                is_auction_sheet=True,
                is_readable=True,
                complexity=LayoutComplexity.COMPLEX_OR_HANDWRITTEN,
                model_used=self.decision_model,
                duration_ms=0,
                warning=None,
            )

        t0 = time.perf_counter()
        resolved_mime = mime_type or detect_mime_from_magic_bytes(full_png)
        api_key = ""
        try:
            async with self.key_pool.semaphore:
                api_key = self.key_pool.next_key()
                client = self._get_client(api_key)
                decisions_api = getattr(client, "decisions", None)
                if decisions_api is None:
                    raise RuntimeError("Gemini SDK client.decisions is unavailable.")

                b64_img = base64.b64encode(full_png).decode("ascii")
                response = await asyncio.to_thread(
                    decisions_api.create,
                    model=self.decision_model,
                    input=[
                        {
                            "type": "image",
                            "data": b64_img,
                            "mime_type": resolved_mime,
                            "resolution": "low",
                        }
                    ],
                    questions={
                        "is_auction_sheet": {
                            "type": "noul",
                            "instructions": (
                                "Is this image a filled-in Japanese car auction inspection sheet for a "
                                "specific vehicle (with actual vehicle data filled in, NOT a blank empty "
                                "template, guide, or car photo)?"
                            ),
                        },
                        "is_readable": {
                            "type": "noul",
                            "instructions": (
                                "Are the filled-in vehicle details (model, mileage, grade) and body "
                                "diagram present and clearly readable for extraction?"
                            ),
                        },
                        "layout_complexity": {
                            "type": "choice",
                            "instructions": "Classify the sheet readability and layout complexity:",
                            "criteria": {
                                "clean_digital": (
                                    "Crisp digital printed sheet with no handwritten notes or tiny circled ovals."
                                ),
                                "complex_or_handwritten": (
                                    "Scan/fax, handwritten inspector/seller notes, circled ovals, or dense diagram."
                                ),
                            },
                        },
                    },
                )
                is_sheet = response.answers["is_auction_sheet"].noul >= self.gatekeeper_sheet_threshold
                is_readable = response.answers["is_readable"].noul >= self.gatekeeper_readable_threshold
                mode = response.answers["layout_complexity"].choice
        except (ServerError, ClientError, TimeoutError, httpx.HTTPError, RuntimeError, AttributeError) as exc:
            if api_key and isinstance(exc, ClientError) and getattr(exc, "code", None) == 429:
                self.key_pool.mark_key_rate_limited(api_key, self.key_cooldown_seconds)
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            if self.gatekeeper_fail_open:
                logger.warning("Gatekeeper %s unavailable (%s); falling back to open mode.", self.decision_model, exc)
                return GatekeeperDecisionEntity(
                    is_auction_sheet=True,
                    is_readable=True,
                    complexity=LayoutComplexity.COMPLEX_OR_HANDWRITTEN,
                    model_used=self.decision_model,
                    duration_ms=elapsed_ms,
                    warning=f"gatekeeper_unavailable:{exc.__class__.__name__}",
                )
            raise

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        complexity = (
            LayoutComplexity.CLEAN_DIGITAL
            if mode == LayoutComplexity.CLEAN_DIGITAL.value
            else LayoutComplexity.COMPLEX_OR_HANDWRITTEN
        )
        return GatekeeperDecisionEntity(
            is_auction_sheet=is_sheet,
            is_readable=is_readable,
            complexity=complexity,
            model_used=self.decision_model,
            duration_ms=elapsed_ms,
            warning=None,
        )

    async def extract_fast_header(self, sliced: SlicedSheetEntity) -> FastHeaderPreviewEntity | None:
        """Run non-blocking low-resolution header OCR with strict timeout (<= 1.2s by default)."""
        t0 = time.perf_counter()
        target_bytes = sliced.crops_png.get("top_left") or sliced.full_png
        mime_type = sliced.mime_type or detect_mime_from_magic_bytes(target_bytes)
        candidates = self._ordered_candidate_models()
        model_name = candidates[0] if candidates else self.flash_model

        async def _call_header() -> FastHeaderPreviewEntity:
            async with self.key_pool.semaphore:
                api_key = self.key_pool.next_key()
                client = self._get_client(api_key)
                contents = [
                    "Быстро извлеки из шапки аукционного листа марку на латинице (make_en), модель на латинице (model_en) и номер лота (lot_number).",
                    _image_part(target_bytes, types.PartMediaResolutionLevel.MEDIA_RESOLUTION_LOW, mime_type),
                ]
                config = types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
                    response_mime_type="application/json",
                    response_json_schema=FastHeaderPreviewSchema.model_json_schema(),
                )
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model_name,
                    contents=contents,
                    config=config,
                )
                if not response.text:
                    raise ValueError("Empty fast header response.")
                parsed = FastHeaderPreviewSchema.model_validate_json(response.text)
                return FastHeaderPreviewEntity(
                    make=parsed.make_en,
                    model=parsed.model_en,
                    lot_number=parsed.lot_number,
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                )

        try:
            return await asyncio.wait_for(_call_header(), timeout=self.fast_header_timeout_seconds)
        except (TimeoutError, ClientError, ServerError, RuntimeError, ValueError, OSError, httpx.HTTPError) as exc:
            logger.debug("Fast header preview skipped (%s).", exc)
            return None

    async def _call_model_generate(
        self,
        model_name: str,
        contents: list[str | types.Part],
        thinking_level: types.ThinkingLevel,
        api_key: str,
    ) -> RawExtractionEntity:
        """Execute a single generate_content call and map validated JSON to RawExtractionEntity."""
        client = self._get_client(api_key)
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            thinking_config=types.ThinkingConfig(thinking_level=thinking_level),
            response_mime_type="application/json",
            response_json_schema=AuctionExtractionSchema.model_json_schema(),
        )
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model_name,
            contents=contents,
            config=config,
        )
        if not response.text:
            raise ValueError(f"Gemini Vision API ({model_name}) returned an empty response text.")

        parsed = AuctionExtractionSchema.model_validate_json(response.text)
        entity = to_raw_extraction_entity(parsed)
        return replace(entity, model_used=model_name)

    async def _try_single_model(
        self,
        candidate_model: str,
        contents: list[str | types.Part],
        configured_level: types.ThinkingLevel,
        attempts: list[ModelAttemptEntity],
    ) -> RawExtractionEntity:
        """Execute extraction on a single candidate model with key rotation and cooldown handling."""
        active_level = configured_level
        max_key_tries = (
            max(1, min(self.key_pool.key_count, self.max_key_tries)) if self.key_pool.key_count > 1 else 1
        )
        last_exc: Exception | None = None

        for key_attempt in range(max_key_tries):
            t0 = time.perf_counter()
            async with self.key_pool.semaphore:
                api_key = self.key_pool.next_key()
                try:
                    entity = await self._call_model_generate(
                        model_name=candidate_model,
                        contents=contents,
                        thinking_level=active_level,
                        api_key=api_key,
                    )
                    attempts.append(
                        ModelAttemptEntity(
                            model=candidate_model,
                            status="ok",
                            ms=int((time.perf_counter() - t0) * 1000),
                        )
                    )
                    return entity
                except ClientError as exc:
                    last_exc = exc
                    status_code = getattr(exc, "code", None)
                    if (
                        status_code == 400
                        and "Thinking level" in str(exc)
                        and active_level != types.ThinkingLevel.LOW
                    ):
                        logger.warning(
                            "Model %s rejected %s; downgrading ThinkingLevel to LOW.",
                            candidate_model,
                            active_level,
                        )
                        active_level = types.ThinkingLevel.LOW
                        try:
                            entity = await self._call_model_generate(
                                model_name=candidate_model,
                                contents=contents,
                                thinking_level=active_level,
                                api_key=api_key,
                            )
                            attempts.append(
                                ModelAttemptEntity(
                                    model=candidate_model,
                                    status="ok",
                                    ms=int((time.perf_counter() - t0) * 1000),
                                )
                            )
                            return entity
                        except (ServerError, ClientError, TimeoutError, httpx.HTTPError) as retry_exc:
                            exc = retry_exc
                            last_exc = retry_exc
                            status_code = getattr(retry_exc, "code", None)

                    attempt_ms = int((time.perf_counter() - t0) * 1000)
                    if status_code == 429:
                        attempts.append(ModelAttemptEntity(model=candidate_model, status="error_429", ms=attempt_ms))
                        self.key_pool.mark_key_rate_limited(api_key, self.key_cooldown_seconds)
                        logger.warning(
                            "Model %s rate-limited key (429), attempt %s/%s.",
                            candidate_model,
                            key_attempt + 1,
                            max_key_tries,
                        )
                        if key_attempt + 1 < max_key_tries:
                            continue
                        self._mark_model_cooldown(candidate_model, self.model_cooldown_seconds)
                        break

                    if status_code in (400, 404):
                        attempts.append(ModelAttemptEntity(model=candidate_model, status=f"error_{status_code}", ms=attempt_ms))
                        logger.warning("Model %s rejected request (%s); putting on cooldown.", candidate_model, exc)
                        self._mark_model_cooldown(candidate_model, self.client_error_cooldown_seconds)
                        break

                    attempts.append(ModelAttemptEntity(model=candidate_model, status=f"error_{status_code or 'client'}", ms=attempt_ms))
                    raise
                except (ServerError, TimeoutError, httpx.TimeoutException, httpx.TransportError) as exc:
                    last_exc = exc
                    status_code = getattr(exc, "code", None)
                    attempt_ms = int((time.perf_counter() - t0) * 1000)
                    attempts.append(
                        ModelAttemptEntity(
                            model=candidate_model,
                            status=f"error_{status_code}" if status_code else f"error_{exc.__class__.__name__}",
                            ms=attempt_ms,
                        )
                    )
                    logger.warning(
                        "Model %s failed transiently (%s); switching to next fallback model.",
                        candidate_model,
                        exc,
                    )
                    self._mark_model_cooldown(candidate_model, self.model_cooldown_seconds)
                    break

        assert last_exc is not None
        raise last_exc

    async def extract_sheet(
        self,
        sliced: SlicedSheetEntity,
        complexity: LayoutComplexity,
    ) -> RawExtractionEntity:
        """Extract structured auction sheet data via Gemini Vision with deadline, hedging, and failover."""
        contents = _build_extraction_contents(sliced, complexity)
        configured_level = _resolve_thinking_level(self.thinking_level)
        candidates = self._ordered_candidate_models()
        extract_t0 = time.perf_counter()
        deadline = time.monotonic() + self.request_deadline_seconds
        attempts: list[ModelAttemptEntity] = []
        last_error: Exception | None = None

        index = 0
        while index < len(candidates):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                last_error = TimeoutError(f"Extraction deadline ({self.request_deadline_seconds}s) exceeded.")
                break

            primary_model = candidates[index]
            # Hedge primary with next candidate model when hedge_delay_seconds elapses before completion.
            if index + 1 < len(candidates) and remaining > self.hedge_delay_seconds:
                hedge_model = candidates[index + 1]
                primary_task = asyncio.create_task(
                    self._try_single_model(primary_model, contents, configured_level, attempts)
                )
                done, _pending = await asyncio.wait({primary_task}, timeout=self.hedge_delay_seconds)
                if primary_task in done:
                    try:
                        entity = primary_task.result()
                        return replace(
                            entity,
                            extract_ms=int((time.perf_counter() - extract_t0) * 1000),
                            attempts=list(attempts),
                        )
                    except (ClientError, ServerError, TimeoutError, httpx.HTTPError) as exc:
                        last_error = exc
                        index += 1
                        continue

                hedge_task = asyncio.create_task(
                    self._try_single_model(hedge_model, contents, configured_level, attempts)
                )
                active: set[asyncio.Task[RawExtractionEntity]] = {primary_task, hedge_task}
                try:
                    while active:
                        rem = deadline - time.monotonic()
                        if rem <= 0:
                            last_error = TimeoutError(f"Extraction deadline ({self.request_deadline_seconds}s) exceeded.")
                            break
                        finished, active = await asyncio.wait(
                            active,
                            timeout=rem,
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        if not finished:
                            last_error = TimeoutError(f"Extraction deadline ({self.request_deadline_seconds}s) exceeded.")
                            break
                        for task in finished:
                            exc = task.exception()
                            if exc is None:
                                entity = task.result()
                                for loser in active:
                                    loser.cancel()
                                if active:
                                    await asyncio.gather(*active, return_exceptions=True)
                                    attempts.append(
                                        ModelAttemptEntity(
                                            model=hedge_model if task is primary_task else primary_model,
                                            status="hedged_cancelled",
                                            ms=int((time.perf_counter() - extract_t0) * 1000),
                                        )
                                    )
                                return replace(
                                    entity,
                                    extract_ms=int((time.perf_counter() - extract_t0) * 1000),
                                    attempts=list(attempts),
                                )
                            if isinstance(exc, ClientError) and getattr(exc, "code", None) not in (400, 404, 429):
                                for loser in active:
                                    loser.cancel()
                                if active:
                                    await asyncio.gather(*active, return_exceptions=True)
                                raise exc
                            last_error = exc if isinstance(exc, Exception) else RuntimeError(str(exc))
                finally:
                    for leftover in active:
                        leftover.cancel()
                    if active:
                        await asyncio.gather(*active, return_exceptions=True)

                index += 2
                continue

            try:
                entity = await asyncio.wait_for(
                    self._try_single_model(primary_model, contents, configured_level, attempts),
                    timeout=remaining,
                )
                return replace(
                    entity,
                    extract_ms=int((time.perf_counter() - extract_t0) * 1000),
                    attempts=list(attempts),
                )
            except TimeoutError as exc:
                last_error = TimeoutError(f"Extraction deadline ({self.request_deadline_seconds}s) exceeded.")
                self._mark_model_cooldown(primary_model, self.model_cooldown_seconds)
                if deadline - time.monotonic() <= 0:
                    raise last_error from exc
            except (ClientError, ServerError, httpx.HTTPError) as exc:
                if isinstance(exc, ClientError) and getattr(exc, "code", None) not in (400, 404, 429):
                    raise
                last_error = exc
            index += 1

        if isinstance(last_error, TimeoutError):
            raise last_error
        raise RuntimeError(
            f"All Gemini models failed ({', '.join(self._model_chain)}). Last error: {last_error}"
        ) from last_error
