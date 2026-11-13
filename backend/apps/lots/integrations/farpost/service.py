"""Estimate parts and STO work, then atomically persist the existing repair contract."""

import hashlib
import json
import logging
from dataclasses import asdict
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from django.utils import timezone

from apps.core.enums import ExternalCacheSource, WorkType
from apps.core.models import ExternalCache
from apps.lots.integrations.farpost.client import (
    FarpostClient,
    FarpostFetchError,
    PartCriteria,
    PartOffer,
)

logger = logging.getLogger(__name__)

# Each panel has a single query identity; fixed panels require restoration instead.
PANELS = {
    "front_bumper": ("Передний бампер", "бампер", "", "передний"),
    "rear_bumper": ("Задний бампер", "бампер", "", "задний"),
    "hood": ("Капот", "капот", "", ""),
    "tailgate": ("Крышка багажника", "багажник", "", ""),
    "front_left_fender": ("Переднее левое крыло", "крыло", "левое", "переднее"),
    "front_right_fender": ("Переднее правое крыло", "крыло", "правое", "переднее"),
    "front_left_door": ("Передняя левая дверь", "дверь", "левая", "передняя"),
    "front_right_door": ("Передняя правая дверь", "дверь", "правая", "передняя"),
    "rear_left_door": ("Задняя левая дверь", "дверь", "левая", "задняя"),
    "rear_right_door": ("Задняя правая дверь", "дверь", "правая", "задняя"),
    "windshield": ("Лобовое стекло", "стекло", "", "лобовое"),
}
FIXED_PANELS = {
    "roof": "Крыша",
    "rear_left_quarter": "Заднее левое крыло",
    "rear_right_quarter": "Заднее правое крыло",
    "left_sill": "Левый порог",
    "right_sill": "Правый порог",
}
LABELS = {
    WorkType.MOUNT_DISMOUNT: "Снятие и монтаж",
    WorkType.PAINT: "Покраска с материалами",
    WorkType.PDR_AND_POLISH: "PDR / полировка",
    WorkType.BODYWORK: "Кузовное восстановление",
}


@lru_cache
def repair_matrix() -> dict:
    return json.loads((Path(__file__).parent / "data/repair_matrix.json").read_text())


def _cache_key(criteria: PartCriteria) -> str:
    identity = json.dumps(asdict(criteria), sort_keys=True, ensure_ascii=True).encode()
    return "farpost:parts:v1:" + hashlib.sha256(identity).hexdigest()


def _read_offers(entry: ExternalCache | None) -> list[PartOffer] | None:
    if entry is None or not isinstance(entry.payload, dict):
        return None
    try:
        rows = entry.payload["offers"]
        if not isinstance(rows, list):
            return None
        offers = [PartOffer(**row) for row in rows]
        if any(
            type(o.price_rub) is not int
            or o.price_rub <= 0
            or not o.offer_id
            or type(o.color_matched) is not bool
            or not isinstance(o.url, str)
            or not isinstance(o.title, str)
            for o in offers
        ):
            return None
        return offers
    except (KeyError, TypeError, ValueError):
        return None


def search_cached(
    client: FarpostClient,
    criteria: PartCriteria,
    *,
    deadline: float,
) -> tuple[list[PartOffer], bool]:
    """Keep successful offers separate from short-lived valid empty results."""
    key = _cache_key(criteria)
    entry = ExternalCache.objects.filter(key=key, source=ExternalCacheSource.FARPOST).first()
    offers = _read_offers(entry)
    if offers is not None and not entry.is_expired:
        return offers, False
    empty = ExternalCache.objects.filter(key=key + ":empty").first()
    if empty is not None and not empty.is_expired:
        return [], False
    try:
        offers = client.search(criteria, deadline=deadline)
    except FarpostFetchError as exc:
        logger.warning("Farpost search failed for %s: %s", criteria.panel_id, exc)
        previous = _read_offers(entry)
        if previous and timedelta(0) <= timezone.now() - entry.updated_at <= timedelta(days=1):
            return previous, True
        return [], True
    if offers:
        ExternalCache.objects.update_or_create(
            key=key,
            defaults={
                "source": ExternalCacheSource.FARPOST,
                "payload": {"offers": [asdict(offer) for offer in offers]},
                "expires_at": timezone.now() + timedelta(hours=1),
            },
        )
        ExternalCache.objects.filter(key=key + ":empty").delete()
    else:
        ExternalCache.objects.update_or_create(
            key=key + ":empty",
            defaults={
                "source": ExternalCacheSource.FARPOST,
                "payload": {"offers": []},
                "expires_at": timezone.now() + timedelta(minutes=10),
            },
        )
    return offers, False
