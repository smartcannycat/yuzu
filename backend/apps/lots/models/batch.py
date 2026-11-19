"""Batch upload and processing queue models."""

from __future__ import annotations

import uuid

from django.core.files.storage import storages
from django.core.signals import setting_changed
from django.db import models
from django.dispatch import receiver

from apps.core.enums import BatchStatus, ItemProcessingStatus, TaskStep
from apps.lots.models import _batch_item_upload_to
from apps.lots.models.lot import Lot
from apps.users.models import User


def _get_private_intake_storage():
    return storages["private_intake"]


class Batch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="batches")
    status = models.CharField(
        max_length=20,
        choices=BatchStatus.choices,
        default=BatchStatus.QUEUED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lots_batches"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self) -> str:
        return str(self.id)


class BatchItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="items")
    lot = models.OneToOneField(
        Lot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batch_item",
    )
    file_index = models.IntegerField()
    original_filename = models.CharField(max_length=255)
    original_file = models.FileField(
        upload_to=_batch_item_upload_to,
        storage=_get_private_intake_storage,
    )
    preview_title = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=ItemProcessingStatus.choices,
        default=ItemProcessingStatus.QUEUED,
    )
    current_step = models.CharField(
        max_length=30,
        choices=TaskStep.choices,
        default=TaskStep.GATEKEEPER,
    )
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lots_batch_items"
        ordering = ["file_index"]
        unique_together = [("batch", "file_index")]
        indexes = [
            models.Index(fields=["batch", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.batch_id} [{self.file_index}] {self.original_filename}"


@receiver(setting_changed)
def _refresh_batch_item_storage(*, setting: str, **_kwargs: object) -> None:
    if setting in {"STORAGES", "PRIVATE_INTAKE_ROOT"}:
        BatchItem._meta.get_field("original_file").storage = _get_private_intake_storage()
