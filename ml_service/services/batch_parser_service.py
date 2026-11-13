"""Application service for asynchronous multi-sheet batch parsing jobs."""

import asyncio
import time
from datetime import UTC, datetime
from uuid import uuid4

from ml_service.domains.entities import BatchItemStatusEntity, BatchJobEntity
from ml_service.domains.enums import BatchItemState, ParseStatus, TaskStep
from ml_service.services.sheet_parser_service import ImageLoaderProtocol, SheetParserService


class BatchConflictError(RuntimeError):
    """Raised when attempting to mutate a terminal/completed batch job."""


class BatchCapacityError(RuntimeError):
    """Raised when active in-memory batch store capacity is exhausted."""


class BatchParserService:
    """Manages bounded in-memory batch jobs with TTL eviction and async background tasks."""

    def __init__(
        self,
        parser_service: SheetParserService,
        max_items_per_batch: int = 10,
        max_concurrency: int = 3,
        image_loader: ImageLoaderProtocol | None = None,
        ttl_seconds: float = 1800.0,
        max_batches: int = 200,
    ) -> None:
        self._parser_service = parser_service
        self._image_loader = image_loader
        self._max_items_per_batch = max_items_per_batch
        self._ttl_seconds = ttl_seconds
        self._max_batches = max_batches
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._batches: dict[str, BatchJobEntity] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    def _evict_expired_batches(self) -> None:
        """Drop terminal batches older than ttl_seconds to bound memory growth."""
        now = time.monotonic()
        expired_ids = [
            bid
            for bid, job in self._batches.items()
            if job.is_terminal and (now - job.created_monotonic) >= self._ttl_seconds
        ]
        for bid in expired_ids:
            self._batches.pop(bid, None)

    def _ensure_capacity_for_new_batch(self) -> None:
        """Ensure a slot is available by evicting expired/oldest terminal batches or rejecting."""
        self._evict_expired_batches()
        if len(self._batches) < self._max_batches:
            return
        terminal_oldest = sorted(
            ((job.created_monotonic, bid) for bid, job in self._batches.items() if job.is_terminal),
            key=lambda item: item[0],
        )
        for _, bid in terminal_oldest:
            self._batches.pop(bid, None)
            if len(self._batches) < self._max_batches:
                return
        raise BatchCapacityError(
            f"Batch queue capacity reached ({self._max_batches} active batches). Retry shortly."
        )

    async def _validate_items(self, items: list[tuple[bytes, str]]) -> None:
        """Synchronously validate image bytes, sizes, and MIME signatures before enqueueing."""
        if self._image_loader is None:
            return
        for data, filename in items:
            await self._image_loader.load_from_bytes(data, filename=filename)

    async def create_batch(
        self,
        items: list[tuple[bytes, str]],
        *,
        force_refresh: bool = False,
    ) -> BatchJobEntity:
        """Create a new batch job and start background parsing for all items."""
        if not items or len(items) > self._max_items_per_batch:
            raise ValueError(f"Batch must contain between 1 and {self._max_items_per_batch} files.")
        self._ensure_capacity_for_new_batch()
        await self._validate_items(items)

        batch_id = str(uuid4())
        created_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        batch = BatchJobEntity(batch_id=batch_id, created_at=created_at, items=[])
        self._batches[batch_id] = batch
        self._enqueue_items(batch, items, force_refresh=force_refresh)
        return batch

    async def add_items(
        self,
        batch_id: str,
        items: list[tuple[bytes, str]],
        *,
        force_refresh: bool = False,
    ) -> BatchJobEntity:
        """Append additional sheet images to an active (non-terminal) batch job."""
        batch = self._batches.get(batch_id)
        if batch is None:
            raise KeyError(batch_id)
        if batch.is_terminal:
            raise BatchConflictError(
                f"Batch '{batch_id}' is already {batch.status.value} and cannot accept additional items."
            )
        if not items:
            raise ValueError("At least 1 file must be provided.")
        if len(batch.items) + len(items) > self._max_items_per_batch:
            raise ValueError(
                f"Batch cannot exceed {self._max_items_per_batch} items "
                f"(current={len(batch.items)}, added={len(items)})."
            )
        await self._validate_items(items)

        self._enqueue_items(batch, items, force_refresh=force_refresh)
        return batch

    async def get_batch(self, batch_id: str) -> BatchJobEntity | None:
        """Return the current state of a batch job, or None if unknown/expired."""
        self._evict_expired_batches()
        return self._batches.get(batch_id)

    async def shutdown(self) -> None:
        """Cancel and await all active background parsing tasks."""
        pending = [task for task in self._tasks if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._tasks.clear()

    def _enqueue_items(
        self,
        batch: BatchJobEntity,
        items: list[tuple[bytes, str]],
        *,
        force_refresh: bool,
    ) -> None:
        start_index = len(batch.items)
        for offset, (data, filename) in enumerate(items):
            item_entity = BatchItemStatusEntity(
                lot_id=str(uuid4()),
                file_index=start_index + offset,
                original_filename=filename,
                status=BatchItemState.QUEUED,
                current_step=TaskStep.QUEUED,
                progress_pct=0,
            )
            batch.items.append(item_entity)
            task = asyncio.create_task(
                self._process_item(item_entity, data, force_refresh=force_refresh)
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _process_item(
        self,
        item: BatchItemStatusEntity,
        data: bytes,
        *,
        force_refresh: bool,
    ) -> None:
        async with self._semaphore:
            item.status = BatchItemState.PROCESSING
            item.current_step = TaskStep.GATEKEEPER
            item.progress_pct = 10

            async def _on_step(step: TaskStep, pct: int) -> None:
                item.current_step = step
                item.progress_pct = pct

            async def _on_preview(title: str) -> None:
                item.preview_title = title

            try:
                result = await self._parser_service.parse_bytes(
                    data,
                    item.original_filename,
                    force_refresh=force_refresh,
                    on_step=_on_step,
                    on_preview=_on_preview,
                )
            except Exception as exc:  # noqa: BLE001 - isolate per-item failures inside batch worker
                item.status = BatchItemState.FAILED
                item.current_step = TaskStep.FAILED
                item.lot_id = None
                item.error_message = str(exc) or exc.__class__.__name__
                return

            item.result = result
            if result.status == ParseStatus.REJECTED_NOT_SHEET:
                item.status = BatchItemState.REJECTED_NOT_SHEET
                item.current_step = TaskStep.FAILED
                item.lot_id = None
                item.progress_pct = 100
                item.error_message = "Image rejected by gatekeeper: not a readable auction sheet."
                return

            if not item.preview_title and result.sheet is not None:
                base = " ".join(p for p in (result.sheet.make, result.sheet.model) if p).strip()
                lot = result.sheet.lot_number.strip()
                item.preview_title = f"{base} #{lot}" if base and lot else base or None

            item.status = BatchItemState.READY
            item.current_step = TaskStep.COMPLETED
            item.progress_pct = 100
