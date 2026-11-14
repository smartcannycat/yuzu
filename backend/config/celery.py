"""Celery application configuration for Yuzu background workers and Beat."""

import logging
import os

from celery.signals import worker_ready

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")

logger = logging.getLogger(__name__)

app = Celery("yuzu")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@worker_ready.connect
def _recover_interrupted_batches(**_kwargs: object) -> None:
    from django.conf import settings

    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        return
    try:
        from apps.lots.pipeline import recover_batches_on_startup

        recover_batches_on_startup()
    except Exception:
        logger.exception("Failed to recover interrupted batches on worker startup")
