"""Tests for Celery worker scheduling, recovery, media purge, and Redis hardening."""

from __future__ import annotations

from datetime import timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone
from PIL import Image

from apps.core.enums import BatchStatus, ItemProcessingStatus, TaskStep
from apps.core.exceptions import TooManyRequestsProblemError
from apps.core.redis_utils import acquire_distributed_interval_slot, enforce_rate_limit
from apps.lots.integrations.aleado.client import AleadoClient
from apps.lots.media_purge import purge_stale_media
from apps.lots.models import Batch, BatchItem, Lot
from apps.lots.pipeline import recover_batches_on_startup
from apps.lots.tasks import process_batch_task


class _FakeRedis:
    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.counters: dict[str, int] = {}

    def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> bool:
        if nx and key in self.kv:
            return False
        self.kv[key] = value
        return True

    def eval(self, script: str, numkeys: int, key: str, *args):
        if "INCR" in script:
            next_val = self.counters.get(key, 0) + 1
            self.counters[key] = next_val
            return next_val
        now_ms = int(args[0])
        interval_ms = int(args[1])
        current = self.kv.get(key)
        next_allowed = int(current) if current is not None else now_ms
        if next_allowed < now_ms:
            next_allowed = now_ms
        wait_ms = next_allowed - now_ms
        self.kv[key] = str(next_allowed + interval_ms)
        return wait_ms


def _make_jpeg_bytes() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (64, 64), color=(240, 240, 240)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.django_db
def test_recover_batches_requeues_stuck_batches_without_duplicating_fresh_ones() -> None:
    from apps.users.models import User

    user = User.objects.create_user(email="recover@example.com", password="StrongPassword123")
    stale_batch = Batch.objects.create(user=user, status=BatchStatus.PROCESSING)
    BatchItem.objects.create(
        batch=stale_batch,
        file_index=0,
        original_filename="a.jpg",
        original_file=SimpleUploadedFile("a.jpg", _make_jpeg_bytes(), content_type="image/jpeg"),
        status=ItemProcessingStatus.PROCESSING,
        current_step=TaskStep.GEMINI_OCR,
    )
    fresh_batch = Batch.objects.create(user=user, status=BatchStatus.PROCESSING)
    old_ts = timezone.now() - timedelta(minutes=30)
    Batch.objects.filter(id=stale_batch.id).update(updated_at=old_ts)

    with patch("apps.lots.tasks.process_batch_task.delay") as mock_delay:
        count = recover_batches_on_startup(
            stale_before=timezone.now() - timedelta(minutes=15),
            use_startup_lock=False,
        )

    assert count == 1
    mock_delay.assert_called_once_with(str(stale_batch.id))
    stale_batch.refresh_from_db()
    assert stale_batch.status == BatchStatus.QUEUED
    assert stale_batch.items.get().status == ItemProcessingStatus.QUEUED
    fresh_batch.refresh_from_db()
    assert fresh_batch.status == BatchStatus.PROCESSING


def test_process_batch_task_delegates_to_run_batch_pipeline() -> None:
    batch_id = "11111111-1111-1111-1111-111111111111"
    with patch("apps.lots.pipeline.run_batch_pipeline") as mock_run:
        process_batch_task(batch_id)
    assert mock_run.call_count == 1
    assert str(mock_run.call_args.args[0]) == batch_id


@pytest.mark.django_db
def test_purge_stale_media_cleans_only_expired_deleted_lots_and_old_uploads(settings) -> None:
    from apps.users.models import User

    user = User.objects.create_user(email="purge@example.com", password="StrongPassword123")
    old_deleted_lot = Lot.objects.create(
        user=user,
        deleted_at=timezone.now() - timedelta(days=10),
        sheet_scan=SimpleUploadedFile("scan.jpg", _make_jpeg_bytes(), content_type="image/jpeg"),
        sheet_thumbnail=SimpleUploadedFile(
            "thumb.jpg", _make_jpeg_bytes(), content_type="image/jpeg"
        ),
    )
    recent_deleted_lot = Lot.objects.create(
        user=user,
        deleted_at=timezone.now() - timedelta(days=1),
        sheet_scan=SimpleUploadedFile("keep.jpg", _make_jpeg_bytes(), content_type="image/jpeg"),
    )

    finished_batch = Batch.objects.create(user=user, status=BatchStatus.COMPLETED)
    Batch.objects.filter(id=finished_batch.id).update(
        updated_at=timezone.now() - timedelta(hours=30)
    )
    old_item = BatchItem.objects.create(
        batch=finished_batch,
        file_index=0,
        original_filename="orig.jpg",
        original_file=SimpleUploadedFile("orig.jpg", _make_jpeg_bytes(), content_type="image/jpeg"),
        status=ItemProcessingStatus.READY,
        current_step=TaskStep.COMPLETED,
    )

    old_scan_path = Path(old_deleted_lot.sheet_scan.path)
    keep_scan_path = Path(recent_deleted_lot.sheet_scan.path)
    old_item_path = Path(old_item.original_file.path)
    assert old_scan_path.exists() and keep_scan_path.exists() and old_item_path.exists()

    res = purge_stale_media(deleted_after_days=7, originals_after_hours=24)
    assert res == {"deleted_lots_files": 2, "batch_originals_files": 1}
    assert not old_scan_path.exists()
    assert keep_scan_path.exists()
    assert not old_item_path.exists()

    call_command("purge_media", "--deleted-days=7", "--originals-hours=24")


def test_redis_rate_limiter_and_distributed_aleado_slot(settings) -> None:
    fake = _FakeRedis()
    settings.RATE_LIMIT_ENABLED = True
    with patch("apps.core.redis_utils.get_redis_client", return_value=fake):
        enforce_rate_limit("auth:login", "1.2.3.4", limit=2, window_sec=60, detail="limit")
        enforce_rate_limit("auth:login", "1.2.3.4", limit=2, window_sec=60, detail="limit")
        with pytest.raises(TooManyRequestsProblemError):
            enforce_rate_limit("auth:login", "1.2.3.4", limit=2, window_sec=60, detail="limit")

        first_wait = acquire_distributed_interval_slot("yuzu:aleado:next", 1.0)
        second_wait = acquire_distributed_interval_slot("yuzu:aleado:next", 1.0)
        assert first_wait == 0.0
        assert second_wait is not None and second_wait > 0.5

    # MockTransport isolates unit tests from Redis even if configured
    slept: list[float] = []
    transport = httpx.MockTransport(lambda _req: httpx.Response(200, text="Sign out"))
    with patch(
        "apps.lots.integrations.aleado.client.acquire_distributed_interval_slot"
    ) as mock_slot:
        client = AleadoClient(
            transport=transport,
            request_interval_sec=0.5,
            sleep_fn=slept.append,
        )
        client._throttle()
        mock_slot.assert_not_called()
