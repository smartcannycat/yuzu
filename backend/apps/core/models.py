from datetime import timedelta

from django.db import models
from django.utils import timezone

from apps.core.enums import ExternalCacheSource


class ExternalCache(models.Model):
    """Read-through cache entry for external API responses (CBRF, Drom, Farpost, AucJP)."""

    key = models.CharField(max_length=512, primary_key=True)
    source = models.CharField(max_length=20, choices=ExternalCacheSource.choices)
    payload = models.JSONField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_external_cache"
        ordering = ["-updated_at"]

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()

    @classmethod
    def default_ttl(cls) -> timedelta:
        return timedelta(hours=1)

    def __str__(self) -> str:
        return self.key
