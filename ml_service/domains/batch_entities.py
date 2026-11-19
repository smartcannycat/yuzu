import time
from dataclasses import dataclass, field

from ml_service.domains.entities import ParserResultEntity
from ml_service.domains.enums import BatchItemState, BatchStatus, TaskStep


@dataclass(slots=True)
class BatchItemStatusEntity:
    """Mutable state of a single sheet inside a batch processing queue."""

    lot_id: str | None
    file_index: int
    original_filename: str
    status: BatchItemState
    current_step: TaskStep
    progress_pct: int
    preview_title: str | None = None
    error_message: str | None = None
    result: ParserResultEntity | None = None


@dataclass(slots=True)
class BatchJobEntity:
    """Mutable state of an asynchronous multi-sheet batch (up to 10 sheets)."""

    batch_id: str
    created_at: str
    items: list[BatchItemStatusEntity] = field(default_factory=list)
    created_monotonic: float = field(default_factory=time.monotonic)
    completed_monotonic: float | None = None

    @property
    def total_items(self) -> int:
        return len(self.items)

    @property
    def total_count(self) -> int:
        return len(self.items)

    @property
    def ready_count(self) -> int:
        return sum(1 for item in self.items if item.status == BatchItemState.READY)

    @property
    def failed_count(self) -> int:
        return sum(1 for item in self.items if item.status == BatchItemState.FAILED)

    @property
    def rejected_count(self) -> int:
        return sum(1 for item in self.items if item.status == BatchItemState.REJECTED_NOT_SHEET)

    @property
    def processed_count(self) -> int:
        return self.ready_count + self.failed_count + self.rejected_count

    @property
    def status(self) -> BatchStatus:
        if not self.items:
            return BatchStatus.QUEUED
        if all(item.status == BatchItemState.QUEUED for item in self.items):
            return BatchStatus.QUEUED
        if self.processed_count < self.total_items:
            return BatchStatus.PROCESSING
        if self.ready_count == 0 and (self.failed_count + self.rejected_count) > 0:
            return BatchStatus.FAILED
        if (self.failed_count + self.rejected_count) > 0:
            return BatchStatus.PARTIAL_FAILED
        return BatchStatus.COMPLETED

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            BatchStatus.COMPLETED,
            BatchStatus.PARTIAL_FAILED,
            BatchStatus.FAILED,
        }
