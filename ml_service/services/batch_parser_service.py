"""Application service for asynchronous multi-sheet batch parsing jobs."""

import asyncio
import logging
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from ml_service.domains.batch_entities import BatchItemStatusEntity, BatchJobEntity
from ml_service.domains.enums import BatchItemState, ParseStatus, TaskStep
from ml_service.services.batch_spill import (
    BatchSpillStore,
    StagedBatchItem,
    sanitize_batch_error,
    unlink_quiet,
)
from ml_service.services.sheet_parser_service import ImageLoaderProtocol, SheetParserService

logger = logging.getLogger(__name__)


class BatchConflictError(RuntimeError):
    """Raised when attempting to mutate a terminal/completed batch job."""


class BatchCapacityError(RuntimeError):
    """Raised when active batch count or global queued-byte capacity is exhausted."""


class BatchParserService:
    """Manages bounded batch jobs with disk spill, queued-byte cap, and completion-based TTL."""

    def __init__(
        self,
        parser_service: SheetParserService,
        max_items_per_batch: int = 10,
        max_concurrency: int = 3,
        image_loader: ImageLoaderProtocol | None = None,
        ttl_seconds: float = 1800.0,
        max_batches: int = 200,
        cache_dir: Path | None = None,
        max_queued_bytes: int = 256 * 1024 * 1024,
    ) -> None:
        self._parser_service = parser_service
        self._image_loader = image_loader
        self._max_items_per_batch = max_items_per_batch
        self._ttl_seconds = ttl_seconds
        self._max_batches = max_batches
        self._max_queued_bytes = max(1, max_queued_bytes)
        self._spill_store = BatchSpillStore(cache_dir=cache_dir)
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._batches: dict[str, BatchJobEntity] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._queued_bytes: int = 0

    @property
    def queued_bytes(self) -> int:
        return self._queued_bytes

    @property
    def remaining_queued_bytes(self) -> int:
        return max(0, self._max_queued_bytes - self._queued_bytes)

    def _evict_expired_batches(self) -> None:
        """Drop terminal batches whose completion TTL has elapsed."""
        now = time.monotonic()
        expired_ids: list[str] = []
        for bid, job in self._batches.items():
            if not job.is_terminal:
                continue
            if job.completed_monotonic is None:
                job.completed_monotonic = now
            if (now - job.completed_monotonic) >= self._ttl_seconds:
                expired_ids.append(bid)
        for bid in expired_ids:
            self._batches.pop(bid, None)

    def _ensure_capacity_for_new_batch(self) -> None:
        """Ensure a slot is available by evicting expired/oldest terminal batches or rejecting."""
        self._evict_expired_batches()
        if len(self._batches) < self._max_batches:
            return
        terminal_oldest = sorted(
            (
                (job.completed_monotonic or job.created_monotonic, bid)
                for bid, job in self._batches.items()
                if job.is_terminal
            ),
            key=lambda item: item[0],
        )
        for _, bid in terminal_oldest:
            self._batches.pop(bid, None)
            if len(self._batches) < self._max_batches:
                return
        raise BatchCapacityError(
            f"Batch queue capacity reached ({self._max_batches} active batches). Retry shortly."
        )

    def _ensure_queued_bytes_capacity(self, additional_bytes: int) -> None:
        if additional_bytes < 0 or (self._queued_bytes + additional_bytes) > self._max_queued_bytes:
            raise BatchCapacityError(
                f"Batch queued byte cap reached ({self._max_queued_bytes} bytes). Retry shortly."
            )

    def preflight_create(self, *, item_count: int, declared_bytes: int = 0) -> None:
        """Verify batch count and queued-bytes limits before reading multipart uploads."""
        if item_count < 1 or item_count > self._max_items_per_batch:
            raise ValueError(f"Batch must contain between 1 and {self._max_items_per_batch} files.")
        self._ensure_capacity_for_new_batch()
        self._ensure_queued_bytes_capacity(declared_bytes)

    def preflight_add_items(
        self,
        batch_id: str,
        *,
        item_count: int,
        declared_bytes: int = 0,
    ) -> BatchJobEntity:
        """Verify target batch state, item count, and queued-bytes limits before reading uploads."""
        self._evict_expired_batches()
        batch = self._batches.get(batch_id)
        if batch is None:
            raise KeyError(batch_id)
        if batch.is_terminal:
            raise BatchConflictError(
                f"Batch '{batch_id}' is already {batch.status.value} "
                "and cannot accept additional items."
            )
        if item_count < 1:
            raise ValueError("At least 1 file must be provided.")
        if len(batch.items) + item_count > self._max_items_per_batch:
            raise ValueError(
                f"Batch cannot exceed {self._max_items_per_batch} items "
                f"(current={len(batch.items)}, added={item_count})."
            )
        self._ensure_queued_bytes_capacity(declared_bytes)
        return batch

    async def stage_upload(
        self,
        data: bytes,
        filename: str,
        *,
        pending_bytes: int = 0,
    ) -> StagedBatchItem:
        """Validate image bytes and spill to a temporary disk file under cache_dir."""
        self._ensure_queued_bytes_capacity(pending_bytes + len(data))
        return await self._spill_store.stage_upload(data, filename, image_loader=self._image_loader)

    async def discard_staged(self, staged_items: Sequence[StagedBatchItem]) -> None:
        """Delete staged spill files that were not enqueued."""
        await self._spill_store.discard_staged(staged_items)

    async def _prepare_staged_items(
        self,
        items: Sequence[tuple[bytes, str] | StagedBatchItem],
    ) -> tuple[list[StagedBatchItem], list[StagedBatchItem]]:
        return await self._spill_store.stage_sequence(
            items,
            image_loader=self._image_loader,
            check_bytes=self._ensure_queued_bytes_capacity,
        )

    async def create_batch(
        self,
        items: Sequence[tuple[bytes, str] | StagedBatchItem],
        *,
        force_refresh: bool = False,
    ) -> BatchJobEntity:
        """Create a new batch job and start background parsing for all items."""
        self.preflight_create(item_count=len(items))
        staged, newly_created = await self._prepare_staged_items(items)
        try:
            self._ensure_capacity_for_new_batch()
            self._ensure_queued_bytes_capacity(sum(item.size for item in staged))
        except BaseException:
            await self.discard_staged(newly_created)
            raise

        batch_id = str(uuid4())
        created_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        batch = BatchJobEntity(batch_id=batch_id, created_at=created_at, items=[])
        self._batches[batch_id] = batch
        self._enqueue_items(batch, staged, force_refresh=force_refresh)
        return batch

    async def add_items(
        self,
        batch_id: str,
        items: Sequence[tuple[bytes, str] | StagedBatchItem],
        *,
        force_refresh: bool = False,
    ) -> BatchJobEntity:
        """Append additional sheet images to an active (non-terminal) batch job."""
        self.preflight_add_items(batch_id, item_count=len(items))
        staged, newly_created = await self._prepare_staged_items(items)
        try:
            batch = self.preflight_add_items(
                batch_id,
                item_count=len(staged),
                declared_bytes=sum(item.size for item in staged),
            )
        except BaseException:
            await self.discard_staged(newly_created)
            raise

        self._enqueue_items(batch, staged, force_refresh=force_refresh)
        return batch

    async def get_batch(self, batch_id: str) -> BatchJobEntity | None:
        """Return the current state of a batch job, or None if unknown/expired."""
        self._evict_expired_batches()
        return self._batches.get(batch_id)

    async def shutdown(self) -> None:
        """Cancel and await all active background parsing tasks and clean up spill files."""
        pending = [task for task in self._tasks if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._tasks.clear()
        await self._spill_store.cleanup_paths()
        self._queued_bytes = 0

    def _enqueue_items(
        self,
        batch: BatchJobEntity,
        staged_items: list[StagedBatchItem],
        *,
        force_refresh: bool,
    ) -> None:
        start_index = len(batch.items)
        for offset, staged in enumerate(staged_items):
            item_entity = BatchItemStatusEntity(
                lot_id=str(uuid4()),
                file_index=start_index + offset,
                original_filename=staged.original_filename,
                status=BatchItemState.QUEUED,
                current_step=TaskStep.QUEUED,
                progress_pct=0,
            )
            batch.items.append(item_entity)
            self._queued_bytes += staged.size
            self._spill_store.active_paths.add(staged.path)
            task = asyncio.create_task(
                self._process_item(
                    batch,
                    item_entity,
                    staged.path,
                    staged.size,
                    force_refresh=force_refresh,
                )
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _process_item(
        self,
        batch: BatchJobEntity,
        item: BatchItemStatusEntity,
        spill_path: Path,
        payload_size: int,
        *,
        force_refresh: bool,
    ) -> None:
        try:
            async with self._semaphore:
                data = await asyncio.to_thread(spill_path.read_bytes)
                await asyncio.to_thread(unlink_quiet, spill_path)

                item.status = BatchItemState.PROCESSING
                item.current_step = TaskStep.GATEKEEPER
                item.progress_pct = 10

                async def _on_step(step: TaskStep, pct: int) -> None:
                    if step == TaskStep.COMPLETED and item.status != BatchItemState.READY:
                        return
                    if step == TaskStep.FAILED and item.status not in {
                        BatchItemState.FAILED,
                        BatchItemState.REJECTED_NOT_SHEET,
                    }:
                        return
                    item.current_step = step
                    item.progress_pct = pct

                try:
                    result = await self._parser_service.parse_bytes(
                        data,
                        item.original_filename,
                        force_refresh=force_refresh,
                        on_step=_on_step,
                    )
                except Exception as exc:
                    logger.exception(
                        "Batch item %s (%s) processing failed",
                        item.file_index,
                        item.original_filename,
                    )
                    item.status = BatchItemState.FAILED
                    item.lot_id = None
                    item.error_message = sanitize_batch_error(exc)
                    await _on_step(TaskStep.FAILED, item.progress_pct)
                    return
                finally:
                    del data

                item.result = result
                if result.status == ParseStatus.REJECTED_NOT_SHEET:
                    item.lot_id = None
                    item.error_message = (
                        "Image rejected by gatekeeper: not a readable auction sheet."
                    )
                    item.status = BatchItemState.REJECTED_NOT_SHEET
                    await _on_step(TaskStep.FAILED, 100)
                    return

                if not item.preview_title and result.sheet is not None:
                    base = " ".join(p for p in (result.sheet.make, result.sheet.model) if p).strip()
                    lot = result.sheet.lot_number.strip()
                    item.preview_title = f"{base} #{lot}" if base and lot else base or None

                item.status = BatchItemState.READY
                await _on_step(TaskStep.COMPLETED, 100)
        finally:
            if batch.is_terminal and batch.completed_monotonic is None:
                batch.completed_monotonic = time.monotonic()
            self._spill_store.active_paths.discard(spill_path)
            await asyncio.to_thread(unlink_quiet, spill_path)
            self._queued_bytes = max(0, self._queued_bytes - payload_size)
