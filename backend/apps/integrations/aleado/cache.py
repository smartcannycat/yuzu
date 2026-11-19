"""Read-through 3-tier Redis cache for Aleado search, detail, and chassis OCR results."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from redis.exceptions import RedisError

from apps.core import redis_utils
from apps.integrations.aleado.parser import AleadoLotDetail, AleadoLotRow

logger = logging.getLogger(__name__)

_CACHE_ERRORS = (RedisError, OSError, ValueError, TypeError, KeyError)


def _search_key(model_code: str, year: int | None) -> str:
    code_norm = model_code.strip().upper()
    year_part = str(year) if year is not None else "any"
    return f"yuzu:aleado:search:{code_norm}:{year_part}"


def _detail_key(internal_id: str) -> str:
    return f"yuzu:aleado:detail:{internal_id}"


def _chassis_key(internal_id: str) -> str:
    return f"yuzu:aleado:chassis:{internal_id}"


def _parse_iso_datetime(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    if not isinstance(raw, str):
        raise TypeError("Expected ISO datetime string")
    return datetime.fromisoformat(raw)


def _serialize_row(row: AleadoLotRow) -> dict[str, Any]:
    return {
        "trading_date": row.trading_date.isoformat() if row.trading_date else None,
        "lot_number": row.lot_number,
        "auction_house": row.auction_house,
        "model_name": row.model_name,
        "grade": row.grade,
        "year": row.year,
        "mileage_km": row.mileage_km,
        "displacement_cc": row.displacement_cc,
        "transmission": row.transmission,
        "color": row.color,
        "model_type": row.model_type,
        "start_price_jpy": row.start_price_jpy,
        "result": row.result,
        "internal_id": row.internal_id,
        "photo_url": row.photo_url,
    }


def _deserialize_row(raw: dict[str, Any]) -> AleadoLotRow:
    return AleadoLotRow(
        trading_date=_parse_iso_datetime(raw.get("trading_date")),
        lot_number=str(raw["lot_number"]),
        auction_house=str(raw["auction_house"]),
        model_name=str(raw["model_name"]),
        grade=raw.get("grade"),
        year=raw.get("year"),
        mileage_km=raw.get("mileage_km"),
        displacement_cc=raw.get("displacement_cc"),
        transmission=raw.get("transmission"),
        color=raw.get("color"),
        model_type=raw.get("model_type"),
        start_price_jpy=raw.get("start_price_jpy"),
        result=raw.get("result"),
        internal_id=raw.get("internal_id"),
        photo_url=raw.get("photo_url"),
    )


def _serialize_detail(detail: AleadoLotDetail) -> dict[str, Any]:
    return {
        "scores": detail.scores,
        "start_price_jpy": detail.start_price_jpy,
        "mileage_km": detail.mileage_km,
        "chassis_image_url": detail.chassis_image_url,
        "model_type": detail.model_type,
        "year": detail.year,
        "auction_house": detail.auction_house,
        "lot_number": detail.lot_number,
        "trading_datetime": (
            detail.trading_datetime.isoformat() if detail.trading_datetime else None
        ),
        "result": detail.result,
        "equipment": detail.equipment,
        "condition": detail.condition,
    }


def _deserialize_detail(raw: dict[str, Any]) -> AleadoLotDetail:
    return AleadoLotDetail(
        scores=raw.get("scores"),
        start_price_jpy=raw.get("start_price_jpy"),
        mileage_km=raw.get("mileage_km"),
        chassis_image_url=raw.get("chassis_image_url"),
        model_type=raw.get("model_type"),
        year=raw.get("year"),
        auction_house=raw.get("auction_house"),
        lot_number=raw.get("lot_number"),
        trading_datetime=_parse_iso_datetime(raw.get("trading_datetime")),
        result=raw.get("result"),
        equipment=raw.get("equipment"),
        condition=raw.get("condition"),
    )


def _decode_redis_text(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        return raw.decode("utf-8")
    if isinstance(raw, str):
        return raw
    raise TypeError("Unexpected Redis payload type")


class AleadoCache:
    """Fail-open 3-tier Redis cache for Aleado lookups and verified chassis IDs."""

    def __init__(
        self,
        *,
        redis_client: Any = None,
        search_ttl_sec: int = 1800,
        detail_ttl_sec: int = 604800,
        chassis_ttl_sec: int = 2592000,
    ) -> None:
        self._redis_client = redis_client
        self.search_ttl_sec = max(0, int(search_ttl_sec))
        self.detail_ttl_sec = max(0, int(detail_ttl_sec))
        self.chassis_ttl_sec = max(0, int(chassis_ttl_sec))

    def _client(self) -> Any | None:
        if self._redis_client is not None:
            return self._redis_client
        return redis_utils.get_redis_client()

    def get_search(self, model_code: str, year: int | None) -> list[AleadoLotRow] | None:
        if self.search_ttl_sec <= 0:
            return None
        client = self._client()
        if client is None:
            return None
        key = _search_key(model_code, year)
        try:
            text = _decode_redis_text(client.get(key))
            if not text:
                return None
            items = json.loads(text)
            if not isinstance(items, list):
                return None
            return [_deserialize_row(item) for item in items]
        except _CACHE_ERRORS as exc:
            logger.debug("Aleado search cache read failed for %s: %s", key, exc)
            return None

    def set_search(self, model_code: str, year: int | None, rows: list[AleadoLotRow]) -> None:
        if self.search_ttl_sec <= 0 or not rows:
            return
        client = self._client()
        if client is None:
            return
        key = _search_key(model_code, year)
        try:
            payload = json.dumps([_serialize_row(row) for row in rows])
            client.set(key, payload, ex=self.search_ttl_sec)
        except _CACHE_ERRORS as exc:
            logger.debug("Aleado search cache write failed for %s: %s", key, exc)

    def get_detail(self, internal_id: str) -> AleadoLotDetail | None:
        if self.detail_ttl_sec <= 0 or not internal_id:
            return None
        client = self._client()
        if client is None:
            return None
        key = _detail_key(internal_id)
        try:
            text = _decode_redis_text(client.get(key))
            if not text:
                return None
            payload = json.loads(text)
            if not isinstance(payload, dict):
                return None
            return _deserialize_detail(payload)
        except _CACHE_ERRORS as exc:
            logger.debug("Aleado detail cache read failed for %s: %s", key, exc)
            return None

    def set_detail(self, internal_id: str, detail: AleadoLotDetail) -> None:
        if self.detail_ttl_sec <= 0 or not internal_id:
            return
        client = self._client()
        if client is None:
            return
        key = _detail_key(internal_id)
        try:
            client.set(key, json.dumps(_serialize_detail(detail)), ex=self.detail_ttl_sec)
        except _CACHE_ERRORS as exc:
            logger.debug("Aleado detail cache write failed for %s: %s", key, exc)

    def get_chassis(self, internal_id: str) -> str | None:
        if self.chassis_ttl_sec <= 0 or not internal_id:
            return None
        client = self._client()
        if client is None:
            return None
        key = _chassis_key(internal_id)
        try:
            text = _decode_redis_text(client.get(key))
            if not text:
                return None
            cleaned = text.strip()
            return cleaned or None
        except _CACHE_ERRORS as exc:
            logger.debug("Aleado chassis cache read failed for %s: %s", key, exc)
            return None

    def set_chassis(self, internal_id: str, frame_id: str) -> None:
        cleaned = (frame_id or "").strip()
        if self.chassis_ttl_sec <= 0 or not internal_id or not cleaned:
            return
        client = self._client()
        if client is None:
            return
        key = _chassis_key(internal_id)
        try:
            client.set(key, cleaned, ex=self.chassis_ttl_sec)
        except _CACHE_ERRORS as exc:
            logger.debug("Aleado chassis cache write failed for %s: %s", key, exc)
