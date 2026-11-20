"""Disk spill storage helpers for bounded batch upload staging."""

import asyncio
import logging
import os
import shutil
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)


class BytesImageLoader(Protocol):
    async def load_from_bytes(self, data: bytes, filename: str = "upload.png") -> object: ...


@dataclass(slots=True, frozen=True)
class StagedBatchItem:
    """Validated batch item spilled to a temporary disk file pending execution."""

    path: Path
    size: int
    original_filename: str


def unlink_quiet(path: Path) -> None:
    """Delete a temporary spill file without raising on missing/locked files."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.debug("Failed to remove temporary spill file %s", path)


def sanitize_batch_error(exc: Exception) -> str:
    """Return a safe external error summary without leaking internal exception messages."""
    if isinstance(exc, ValueError):
        return "Invalid auction sheet image payload."
    return "Failed to process auction sheet image."


class BatchSpillStore:
    """Manages temporary disk files for queued batch items under cache_dir."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        if cache_dir is not None:
            self.spill_dir = Path(cache_dir) / "batch_spill"
            self._owns_spill_dir = False
        else:
            self.spill_dir = Path(tempfile.mkdtemp(prefix="yuzu_ml_batch_"))
            self._owns_spill_dir = True
        self.active_paths: set[Path] = set()

    def write_bytes(self, data: bytes) -> Path:
        """Write raw image bytes to a unique temporary file on disk."""
        self.spill_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=self.spill_dir, prefix="item_", suffix=".bin")
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        return Path(tmp_name)

    async def stage_upload(
        self,
        data: bytes,
        filename: str,
        *,
        image_loader: BytesImageLoader | None = None,
    ) -> StagedBatchItem:
        """Validate image bytes and spill them to disk."""
        if image_loader is not None:
            loaded = await image_loader.load_from_bytes(data, filename=filename)
            clean_name = getattr(loaded, "original_filename", None) or "sheet_image"
        else:
            clean_name = filename.strip() if filename and filename.strip() else "sheet_image"
        spill_path = await asyncio.to_thread(self.write_bytes, data)
        return StagedBatchItem(path=spill_path, size=len(data), original_filename=clean_name)

    async def discard_staged(self, staged_items: Sequence[StagedBatchItem]) -> None:
        """Delete staged spill files that were not enqueued."""
        for staged in staged_items:
            await asyncio.to_thread(unlink_quiet, staged.path)

    async def stage_sequence(
        self,
        items: Sequence[tuple[bytes, str] | StagedBatchItem],
        *,
        image_loader: BytesImageLoader | None,
        check_bytes: Callable[[int], None],
    ) -> tuple[list[StagedBatchItem], list[StagedBatchItem]]:
        """Validate and spill raw tuples into disk-backed StagedBatchItem objects."""
        staged: list[StagedBatchItem] = []
        newly_created: list[StagedBatchItem] = []
        pending_bytes = 0
        try:
            for item in items:
                if isinstance(item, StagedBatchItem):
                    check_bytes(pending_bytes + item.size)
                    staged.append(item)
                    pending_bytes += item.size
                else:
                    data, filename = item
                    check_bytes(pending_bytes + len(data))
                    spilled = await self.stage_upload(data, filename, image_loader=image_loader)
                    staged.append(spilled)
                    newly_created.append(spilled)
                    pending_bytes += spilled.size
        except BaseException:
            await self.discard_staged(newly_created)
            raise
        return staged, newly_created

    async def cleanup_paths(self) -> None:
        """Delete all tracked active spill files and owned temporary directory."""
        for spill_path in list(self.active_paths):
            await asyncio.to_thread(unlink_quiet, spill_path)
        self.active_paths.clear()
        if self._owns_spill_dir and self.spill_dir.exists():
            await asyncio.to_thread(shutil.rmtree, self.spill_dir, True)
