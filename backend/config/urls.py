from django.conf import settings
from django.contrib import admin
from django.urls import path

from config.api import api


def _normalize_admin_url(raw_url: str) -> str:
    cleaned = (raw_url or "").strip().strip("/")
    return f"{cleaned}/" if cleaned else "admin/"


urlpatterns = [
    path(_normalize_admin_url(getattr(settings, "DJANGO_ADMIN_URL", "admin/")), admin.site.urls),
    path("api/v1/", api.urls),
]
