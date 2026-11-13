import asyncio
import base64
from dataclasses import replace
import logging
import time

from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError
import httpx

from app.domains.entities import (
    GatekeeperDecisionEntity,
    RawExtractionEntity,
    SlicedSheetEntity,
)
from app.domains.enums import LayoutComplexity
from app.infrastructure.gemini_schemas import (
    SYSTEM_PROMPT,
    AuctionExtractionSchema,
    to_raw_extraction_entity,
)
from app.infrastructure.key_pool import GeminiKeyPool

logger = logging.getLogger(__name__)

_IS_SHEET_THRESHOLD = 0.60
_IS_READABLE_THRESHOLD = 0.50

_THINKING_LEVELS: dict[str, types.ThinkingLevel] = {
    "MINIMAL": types.ThinkingLevel.MINIMAL,
    "LOW": types.ThinkingLevel.LOW,
    "MEDIUM": types.ThinkingLevel.MEDIUM,
    "HIGH": types.ThinkingLevel.HIGH,
}


def _detect_image_mime_type(data: bytes) -> str:
    """Detect image MIME type from magic bytes with PNG fallback."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


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
    mime_type = sliced.mime_type or _detect_image_mime_type(sliced.full_png)
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
            )

        resolved_mime = mime_type or _detect_image_mime_type(full_png)
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
                is_sheet = response.answers["is_auction_sheet"].noul >= _IS_SHEET_THRESHOLD
                is_readable = response.answers["is_readable"].noul >= _IS_READABLE_THRESHOLD
                mode = response.answers["layout_complexity"].choice
        except (ServerError, ClientError, TimeoutError, httpx.HTTPError) as exc:
            if isinstance(exc, ClientError) and getattr(exc, "code", None) == 429:
                self.key_pool.mark_key_rate_limited(api_key, self.key_cooldown_seconds)
            if self.gatekeeper_fail_open:
                logger.warning("Gatekeeper %s failed (%s); falling back to open mode.", self.decision_model, exc)
                return GatekeeperDecisionEntity(
                    is_auction_sheet=True,
                    is_readable=True,
                    complexity=LayoutComplexity.COMPLEX_OR_HANDWRITTEN,
                )
            raise

        complexity = (
            LayoutComplexity.CLEAN_DIGITAL
            if mode == LayoutComplexity.CLEAN_DIGITAL.value
            else LayoutComplexity.COMPLEX_OR_HANDWRITTEN
        )
        return GatekeeperDecisionEntity(
            is_auction_sheet=is_sheet,
            is_readable=is_readable,
            complexity=complexity,
        )

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

    async def extract_sheet(
        self,
        sliced: SlicedSheetEntity,
        complexity: LayoutComplexity,
    ) -> RawExtractionEntity:
        """Extract structured auction sheet data via Gemini Vision with automatic model failover."""
        contents = _build_extraction_contents(sliced, complexity)
        configured_level = _resolve_thinking_level(self.thinking_level)
        candidates = self._ordered_candidate_models()
        last_error: Exception | None = None

        for candidate_model in candidates:
            active_level = configured_level
            max_key_tries = max(1, min(self.key_pool.key_count, 3)) if self.key_pool.key_count > 1 else 1
            for key_attempt in range(max_key_tries):
                async with self.key_pool.semaphore:
                    api_key = self.key_pool.next_key()
                    try:
                        return await self._call_model_generate(
                            model_name=candidate_model,
                            contents=contents,
                            thinking_level=active_level,
                            api_key=api_key,
                        )
                    except ClientError as exc:
                        last_error = exc
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
                                return await self._call_model_generate(
                                    model_name=candidate_model,
                                    contents=contents,
                                    thinking_level=active_level,
                                    api_key=api_key,
                                )
                            except (ServerError, ClientError, TimeoutError, httpx.HTTPError) as retry_exc:
                                exc = retry_exc
                                last_error = retry_exc
                                status_code = getattr(retry_exc, "code", None)

                        if status_code == 429:
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
                            logger.warning("Model %s rejected request (%s); putting on cooldown.", candidate_model, exc)
                            self._mark_model_cooldown(candidate_model, 300.0)
                            break

                        raise
                    except (ServerError, TimeoutError, httpx.TimeoutException, httpx.TransportError) as exc:
                        last_error = exc
                        logger.warning(
                            "Model %s failed transiently (%s); switching to next fallback model.",
                            candidate_model,
                            exc,
                        )
                        self._mark_model_cooldown(candidate_model, self.model_cooldown_seconds)
                        break

        raise RuntimeError(
            f"All Gemini models failed ({', '.join(self._model_chain)}). Last error: {last_error}"
        ) from last_error
