"""Application service for asynchronous multi-sheet batch parsing jobs."""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from app.domains.entities import BatchItemStatusEntity, BatchJobEntity
from app.domains.enums import BatchItemState
from app.services.sheet_parser_service import SheetParserService


class BatchParserService:
    """Manages in-memory batch jobs of 1..10 auction sheet images with async background tasks."""

    def __init__(
        self,
        parser_service: SheetParserService,
        max_items_per_batch: int = 10,
        max_concurrency: int = 3,
    ) -> None:
        self._parser_service = parser_service
        self._max_items_per_batch = max_items_per_batch
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._batches: dict[str, BatchJobEntity] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    async def create_batch(
        self,
        items: list[tuple[bytes, str]],
        *,
        force_refresh: bool = False,
    ) -> BatchJobEntity:
        """Create a new batch job and start background parsing for all items."""
        if not items or len(items) > self._max_items_per_batch:
            raise ValueError(f"Batch must contain between 1 and {self._max_items_per_batch} files.")

        batch_id = f"batch_{uuid4().hex[:12]}"
        created_at = datetime.now(timezone.utc).isoformat()
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
        """Append additional sheet images to an existing batch job."""
        batch = self._batches.get(batch_id)
        if batch is None:
            raise KeyError(batch_id)
        if not items:
            raise ValueError("At least 1 file must be provided.")
        if len(batch.items) + len(items) > self._max_items_per_batch:
            raise ValueError(
                f"Batch cannot exceed {self._max_items_per_batch} items "
                f"(current={len(batch.items)}, added={len(items)})."
            )

        self._enqueue_items(batch, items, force_refresh=force_refresh)
        return batch

    async def get_batch(self, batch_id: str) -> BatchJobEntity | None:
        """Return the current state of a batch job, or None if unknown."""
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
                lot_id=f"lot_{uuid4().hex[:10]}",
                file_index=start_index + offset,
                original_filename=filename,
                status=BatchItemState.QUEUED,
                current_step="queued",
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
            item.current_step = "starting"
            item.progress_pct = 5

            async def _on_step(step: str, pct: int) -> None:
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
                item.status = BatchItemState.FAILED
                item.current_step = "failed"
                item.error_message = str(exc) or exc.__class__.__name__
                return

            item.result = result
            item.status = BatchItemState.READY
            item.current_step = "completed"
            item.progress_pct = 100
