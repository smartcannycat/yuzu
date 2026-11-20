"""Async Gemini Vision client for gatekeeper classification, fast header, and sheet OCR."""

import asyncio
import logging
import time
from dataclasses import replace

import httpx
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
from ml_service.infrastructure.gemini_prompts import (
    build_extraction_contents,
    build_gatekeeper_payload,
    image_part,
    resolve_thinking_level,
)
from ml_service.infrastructure.gemini_runner import GeminiRunner
from ml_service.infrastructure.gemini_schemas import (
    SYSTEM_PROMPT,
    AuctionExtractionSchema,
    FastHeaderPreviewSchema,
    to_raw_extraction_entity,
)
from ml_service.infrastructure.image_formats import detect_mime_from_magic_bytes
from ml_service.infrastructure.key_pool import GeminiKeyPool

logger = logging.getLogger(__name__)


class AsyncGeminiVisionClient:
    """Async Vision OCR facade delegating client lifecycle and hedging to GeminiRunner."""

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
        runner: GeminiRunner | None = None,
    ) -> None:
        self.decision_model = decision_model
        self.flash_model = flash_model
        self.enable_gatekeeper = enable_gatekeeper
        self.gatekeeper_fail_open = gatekeeper_fail_open
        self.thinking_level = thinking_level
        self.fast_header_timeout_seconds = fast_header_timeout_seconds
        self.gatekeeper_sheet_threshold = gatekeeper_sheet_threshold
        self.gatekeeper_readable_threshold = gatekeeper_readable_threshold
        self.runner = runner or GeminiRunner(
            key_pool=key_pool,
            flash_model=flash_model,
            fallback_models=fallback_models,
            request_timeout_ms=request_timeout_ms,
            sdk_max_attempts=sdk_max_attempts,
            model_cooldown_seconds=model_cooldown_seconds,
            client_error_cooldown_seconds=client_error_cooldown_seconds,
            key_cooldown_seconds=key_cooldown_seconds,
            max_key_tries=max_key_tries,
            request_deadline_seconds=request_deadline_seconds,
            hedge_delay_seconds=hedge_delay_seconds,
        )

    @property
    def key_pool(self) -> GeminiKeyPool:
        return self.runner.key_pool

    @property
    def flash_model_name(self) -> str:
        """Return primary configured Vision extraction model name."""
        return self.flash_model

    async def aclose(self) -> None:
        """Close cached SDK clients managed by the runner."""
        await self.runner.aclose()

    async def check_sheet(
        self, full_png: bytes, mime_type: str | None = None
    ) -> GatekeeperDecisionEntity:
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
        payload = build_gatekeeper_payload(self.decision_model, full_png, resolved_mime)
        used_key = ""
        try:
            async with self.runner.key_pool.acquire() as api_key:
                used_key = api_key
                response = await self.runner.run_decisions(api_key=api_key, payload=payload)
                is_sheet = (
                    response.answers["is_auction_sheet"].noul >= self.gatekeeper_sheet_threshold
                )
                is_readable = (
                    response.answers["is_readable"].noul >= self.gatekeeper_readable_threshold
                )
                mode = response.answers["layout_complexity"].choice
        except (
            ServerError,
            ClientError,
            TimeoutError,
            httpx.HTTPError,
            RuntimeError,
            AttributeError,
        ) as exc:
            if used_key and isinstance(exc, ClientError) and getattr(exc, "code", None) == 429:
                self.runner.key_pool.mark_key_rate_limited(
                    used_key, self.runner.key_cooldown_seconds
                )
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            if self.gatekeeper_fail_open:
                logger.warning(
                    "Gatekeeper %s unavailable (%s); falling back to open mode.",
                    self.decision_model,
                    exc,
                )
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

    async def extract_fast_header(
        self, sliced: SlicedSheetEntity
    ) -> FastHeaderPreviewEntity | None:
        """Run non-blocking low-resolution header OCR with strict timeout (<= 1.2s by default)."""
        t0 = time.perf_counter()
        target_bytes = sliced.crops_png.get("top_left") or sliced.full_png
        mime_type = sliced.mime_type or detect_mime_from_magic_bytes(target_bytes)
        candidates = self.runner.ordered_candidate_models()
        model_name = candidates[0] if candidates else self.flash_model

        async def _invoke_header(
            model: str, api_key: str, level: types.ThinkingLevel
        ) -> FastHeaderPreviewEntity:
            contents = [
                (
                    "Быстро извлеки из шапки аукционного листа марку на латинице (make_en), "
                    "модель на латинице (model_en) и номер лота (lot_number)."
                ),
                image_part(
                    target_bytes, types.PartMediaResolutionLevel.MEDIA_RESOLUTION_LOW, mime_type
                ),
            ]
            config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level=level),
                response_mime_type="application/json",
                response_json_schema=FastHeaderPreviewSchema.model_json_schema(),
            )
            response = await self.runner.generate_content(
                api_key=api_key,
                model_name=model,
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

        async def _call_header() -> FastHeaderPreviewEntity:
            async with self.runner.key_pool.acquire() as api_key:
                return await self.runner.call_with_thinking_downgrade(
                    model_name=model_name,
                    api_key=api_key,
                    configured_level=types.ThinkingLevel.MINIMAL,
                    invoke=_invoke_header,
                )

        try:
            return await asyncio.wait_for(_call_header(), timeout=self.fast_header_timeout_seconds)
        except (
            TimeoutError,
            ClientError,
            ServerError,
            RuntimeError,
            ValueError,
            OSError,
            httpx.HTTPError,
        ) as exc:
            logger.debug("Fast header preview skipped (%s).", exc)
            return None

    async def extract_sheet(
        self,
        sliced: SlicedSheetEntity,
        complexity: LayoutComplexity,
    ) -> RawExtractionEntity:
        """Extract auction sheet data via Gemini Vision with deadline, hedging, and failover."""
        contents = build_extraction_contents(sliced, complexity)
        configured_level = resolve_thinking_level(self.thinking_level)
        extract_t0 = time.perf_counter()
        attempts: list[ModelAttemptEntity] = []

        async def _invoke_model(
            model_name: str, api_key: str, level: types.ThinkingLevel
        ) -> RawExtractionEntity:
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                thinking_config=types.ThinkingConfig(thinking_level=level),
                response_mime_type="application/json",
                response_json_schema=AuctionExtractionSchema.model_json_schema(),
            )
            response = await self.runner.generate_content(
                api_key=api_key,
                model_name=model_name,
                contents=contents,
                config=config,
            )
            if not response.text:
                raise ValueError(
                    f"Gemini Vision API ({model_name}) returned an empty response text."
                )
            parsed = AuctionExtractionSchema.model_validate_json(response.text)
            return replace(to_raw_extraction_entity(parsed), model_used=model_name)

        async def _run_model(model_name: str) -> RawExtractionEntity:
            return await self.runner.try_model_with_keys(
                model_name=model_name,
                configured_level=configured_level,
                attempts=attempts,
                invoke=_invoke_model,
            )

        entity = await self.runner.run_hedged(
            run_model=_run_model,
            attempts=attempts,
            extract_t0=extract_t0,
        )
        return replace(
            entity,
            extract_ms=int((time.perf_counter() - extract_t0) * 1000),
            attempts=list(attempts),
        )
