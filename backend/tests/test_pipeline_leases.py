"""Tests for pipeline per-batch Redis leases, heartbeat, ACKS_LATE recovery, and closing."""

from __future__ import annotations

import uuid
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from PIL import Image
from redis.exceptions import RedisError

from apps.core.enums import BatchStatus, ItemProcessingStatus, TaskStep
from apps.lots.models import Batch, BatchItem
from apps.lots.pipeline import recover_batches_on_startup, run_batch_pipeline
from apps.lots.pipeline.leases import (
    acquire_batch_lease,
    batch_lock_key,
    managed_closing,
    release_batch_lease,
    renew_batch_lease,
)
from apps.lots.pipeline.stages import _advance_step
from config import celery as celery_config


class _FakeLeaseRedis:
    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> bool:
        if nx and key in self.kv:
            return False
        self.kv[key] = value
        if ex is not None:
            self.ttls[key] = ex
        return True

    def exists(self, key: str) -> int:
        return 1 if key in self.kv else 0

    def eval(self, script: str, numkeys: int, key: str, *args):
        token = args[0]
        if self.kv.get(key) != token:
            return 0
        if "EXPIRE" in script:
            self.ttls[key] = int(args[1])
            return 1
        if "DEL" in script:
            del self.kv[key]
            self.ttls.pop(key, None)
            return 1
        return 0


def _jpeg_upload(name: str = "sheet.jpg") -> SimpleUploadedFile:
    buf = BytesIO()
    Image.new("RGB", (64, 64), (240, 240, 240)).save(buf, format="JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


@pytest.mark.django_db
def test_advance_step_updates_batch_heartbeat_and_renews_only_owned_lease(user_factory) -> None:
    user = user_factory(email="heartbeat@example.com")
    batch = Batch.objects.create(user=user, status=BatchStatus.PROCESSING)
    old_ts = timezone.now() - timedelta(minutes=10)
    Batch.objects.filter(pk=batch.pk).update(updated_at=old_ts)
    item = BatchItem.objects.create(
        batch=batch,
        file_index=0,
        original_filename="a.jpg",
        original_file=_jpeg_upload(),
        status=ItemProcessingStatus.PROCESSING,
        current_step=TaskStep.GATEKEEPER,
    )

    fake_redis = _FakeLeaseRedis()
    key = batch_lock_key(batch.id)
    with patch("apps.core.redis_utils.get_redis_client", return_value=fake_redis):
        assert acquire_batch_lease(batch.id, ttl_sec=180) is True
        fake_redis.ttls[key] = 5  # simulate nearing expiration
        try:
            with patch("apps.lots.pipeline.stages._PIPELINE_STEP_DELAY_SEC", 0):
                _advance_step(item, TaskStep.GEMINI_OCR)
            batch.refresh_from_db()
            assert batch.updated_at > old_ts
            assert fake_redis.ttls[key] == 180

            # If another worker took over the key, renew/release must NOT touch it.
            fake_redis.kv[key] = "other-worker-token"
            fake_redis.ttls[key] = 42
            assert renew_batch_lease(batch.id, ttl_sec=180) is False
            assert fake_redis.ttls[key] == 42
        finally:
            release_batch_lease(batch.id)
        assert fake_redis.kv[key] == "other-worker-token"


@pytest.mark.django_db(transaction=True)
def test_run_batch_pipeline_respects_held_lease_and_resumes_processing_batch(user_factory) -> None:
    user = user_factory(email="resume@example.com")
    batch = Batch.objects.create(user=user, status=BatchStatus.PROCESSING)
    done_item = BatchItem.objects.create(
        batch=batch,
        file_index=0,
        original_filename="done.jpg",
        original_file=_jpeg_upload("done.jpg"),
        status=ItemProcessingStatus.READY,
        current_step=TaskStep.COMPLETED,
    )
    orphaned_item = BatchItem.objects.create(
        batch=batch,
        file_index=1,
        original_filename="lost.jpg",
        original_file=_jpeg_upload("lost.jpg"),
        status=ItemProcessingStatus.PROCESSING,
        current_step=TaskStep.GEMINI_OCR,
    )

    fake_redis = _FakeLeaseRedis()
    key = batch_lock_key(batch.id)
    fake_redis.kv[key] = "live-worker-token"

    with patch("apps.core.redis_utils.get_redis_client", return_value=fake_redis):
        # Held by another worker -> skips without altering items or deleting foreign lease.
        run_batch_pipeline(batch.id)
        orphaned_item.refresh_from_db()
        assert orphaned_item.status == ItemProcessingStatus.PROCESSING
        assert fake_redis.kv[key] == "live-worker-token"

        # Now simulate worker death / lease expiry -> redelivery resumes PROCESSING batch!
        fake_redis.kv.pop(key)
        processed_ids: list[uuid.UUID] = []

        def fake_process(claimed_item: BatchItem) -> None:
            processed_ids.append(claimed_item.id)
            claimed_item.status = ItemProcessingStatus.READY
            claimed_item.current_step = TaskStep.COMPLETED
            claimed_item.save(update_fields=["status", "current_step", "updated_at"])

        with patch("apps.lots.pipeline.runner._process_item", side_effect=fake_process):
            run_batch_pipeline(batch.id)

    batch.refresh_from_db()
    done_item.refresh_from_db()
    orphaned_item.refresh_from_db()
    assert processed_ids == [orphaned_item.id]
    assert batch.status == BatchStatus.COMPLETED
    assert done_item.status == ItemProcessingStatus.READY
    assert orphaned_item.status == ItemProcessingStatus.READY
    assert key not in fake_redis.kv


@pytest.mark.django_db(transaction=True)
def test_run_batch_pipeline_handles_missing_batch_and_crash_error_handler_cleanly(
    user_factory,
) -> None:
    fake_redis = _FakeLeaseRedis()
    with patch("apps.core.redis_utils.get_redis_client", return_value=fake_redis):
        missing_id = uuid.uuid4()
        run_batch_pipeline(missing_id)
        assert batch_lock_key(missing_id) not in fake_redis.kv

        user = user_factory(email="crash@example.com")
        batch = Batch.objects.create(user=user, status=BatchStatus.QUEUED)
        item = BatchItem.objects.create(
            batch=batch,
            file_index=0,
            original_filename="boom.jpg",
            original_file=_jpeg_upload(),
            status=ItemProcessingStatus.QUEUED,
            current_step=TaskStep.GATEKEEPER,
        )
        with patch(
            "apps.lots.pipeline.runner._process_item",
            side_effect=RuntimeError("unexpected pipeline crash"),
        ):
            run_batch_pipeline(batch.id)

    batch.refresh_from_db()
    item.refresh_from_db()
    assert batch.status == BatchStatus.FAILED
    assert item.status == ItemProcessingStatus.FAILED
    assert batch_lock_key(batch.id) not in fake_redis.kv


@pytest.mark.django_db
def test_worker_ready_passes_stale_before_and_startup_lock_fails_closed(user_factory) -> None:
    user = user_factory(email="failclosed@example.com")
    stuck = Batch.objects.create(user=user, status=BatchStatus.PROCESSING)
    Batch.objects.filter(pk=stuck.pk).update(updated_at=timezone.now() - timedelta(minutes=30))

    class _BrokenRedis:
        def set(self, *_args, **_kwargs):
            raise RedisError("redis unreachable")

    with (
        patch("apps.core.redis_utils.get_redis_client", return_value=_BrokenRedis()),
        patch("apps.lots.tasks.process_batch_task.delay") as mock_delay,
    ):
        count = recover_batches_on_startup(use_startup_lock=True)

    assert count == 0
    mock_delay.assert_not_called()
    stuck.refresh_from_db()
    assert stuck.status == BatchStatus.PROCESSING

    # Held batch lease also prevents Beat/recovery from requeueing an active batch.
    fake_redis = _FakeLeaseRedis()
    fake_redis.kv[batch_lock_key(stuck.id)] = "active-worker"
    with (
        patch("apps.core.redis_utils.get_redis_client", return_value=fake_redis),
        patch("apps.lots.tasks.process_batch_task.delay") as mock_delay,
    ):
        assert recover_batches_on_startup(use_startup_lock=False) == 0
        mock_delay.assert_not_called()

    # worker_ready signal always passes a stale_before cutoff (~15m) and use_startup_lock=True.
    with (
        override_settings(CELERY_TASK_ALWAYS_EAGER=False, BATCH_RECOVERY_STALE_MINUTES=15),
        patch("apps.lots.pipeline.recover_batches_on_startup") as mock_recover,
    ):
        celery_config._recover_interrupted_batches()

    mock_recover.assert_called_once()
    kwargs = mock_recover.call_args.kwargs
    assert kwargs["use_startup_lock"] is True
    assert kwargs["stale_before"] is not None
    age_sec = (timezone.now() - kwargs["stale_before"]).total_seconds()
    assert 890 <= age_sec <= 910


def test_managed_closing_closes_supported_resources_and_skips_plain_fakes() -> None:
    events: list[str] = []

    class _Closable:
        def close(self) -> None:
            events.append("closed")

    class _PlainFake:
        pass

    with managed_closing(_Closable()) as res:
        assert isinstance(res, _Closable)
    assert events == ["closed"]

    events.clear()
    with pytest.raises(RuntimeError, match="boom"), managed_closing(_Closable()):
        raise RuntimeError("boom")
    assert events == ["closed"]

    with managed_closing(_PlainFake()) as fake:
        assert isinstance(fake, _PlainFake)
