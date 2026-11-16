"""Cross-auction anomaly rule evaluation and outcome assembly."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from django.utils import timezone

from apps.core.enums import AnomalySeverity, CrossAuditStatus, RiskLevel
from apps.lots.models import AnomalyAlert, Lot, PastAuctionRecord

if TYPE_CHECKING:
    from datetime import datetime

    from apps.integrations.aleado.parser import AleadoLotDetail, AleadoLotRow

SOURCE_NAME = "Aleado.com"
_REPAIRED_GRADE_RE = re.compile(r"^(?:R[A-Z0-9]*|0|1|2|99|\*{2,3})$")
_NUMERIC_GRADE_RE = re.compile(r"^\d(?:\.\d)?$")
_MAX_HISTORY_ROWS = 20


@dataclass(frozen=True)
class CrossAuditOutcome:
    """Result of one Aleado cross-audit run (maps to CrossAuditReport)."""

    status: CrossAuditStatus
    risk_level: RiskLevel
    has_critical_anomaly: bool
    headline_ru: str
    times_auctioned: int
    is_archive_available: bool
    source_name: str = SOURCE_NAME
    history: list[PastAuctionRecord] = field(default_factory=list)
    anomalies: list[AnomalyAlert] = field(default_factory=list)


@dataclass(frozen=True)
class _VerifiedRow:
    """A candidate row whose chassis number matched the audited lot."""

    row: AleadoLotRow
    detail: AleadoLotDetail | None = None


def _parse_grade(value: str | None) -> float | None:
    cleaned = (value or "").upper().strip()
    if not cleaned:
        return None
    if cleaned == "S":
        return 6.0
    if not _NUMERIC_GRADE_RE.fullmatch(cleaned):
        return None
    return float(cleaned)


def _is_repaired_grade(value: str | None) -> bool:
    return bool(_REPAIRED_GRADE_RE.fullmatch((value or "").upper().strip()))


def _format_date(value: Any) -> str:
    return value.strftime("%d.%m.%Y") if value is not None else "-"


def _safe_archive_url(photo_url: str | None) -> str | None:
    """Allowlist-check a photo URL scraped from Aleado markup."""
    if not photo_url:
        return None
    parsed = urlparse(photo_url)
    if parsed.scheme == "https" and parsed.hostname in {
        "p3.aleado.com",
        "auc.aleado.com",
    }:
        return photo_url[:500]
    return None


def _evaluate_rules(lot: Lot, rows: list[_VerifiedRow]) -> list[AnomalyAlert]:
    """Apply the anomaly detection cascade to verified past rows."""
    alerts: list[AnomalyAlert] = []
    our_grade_num = _parse_grade(lot.overall_grade)

    for verified in rows:
        row = verified.row
        past_house = row.auction_house or "unknown auction"
        past_lot = row.lot_number or "?"
        past_date = _format_date(row.trading_date)
        context = {
            "past_auction_house": past_house,
            "past_lot_number": past_lot,
            "past_auction_date": (
                row.trading_date.strftime("%Y-%m-%d") if row.trading_date else None
            ),
            "past_grade": row.grade,
            "past_mileage_km": row.mileage_km,
            "current_grade": lot.overall_grade,
            "current_mileage_km": lot.mileage_km,
            "chassis_match": "chassis_image_verified",
        }

        if _is_repaired_grade(row.grade) and our_grade_num is not None and our_grade_num >= 3.5:
            alerts.append(
                AnomalyAlert(
                    type="grade_regression",
                    severity=AnomalySeverity.CRITICAL,
                    title_ru="Скрытый аварийный ремонт",
                    message_ru=(
                        f"Прошлый лот {past_house} #{past_lot} ({past_date}) имел оценку "
                        f"{row.grade}, текущая оценка {lot.overall_grade}. Вероятен скрытый "
                        "кузовной ремонт между торгами"
                    ),
                    diff_details=context,
                )
            )

        if (
            row.mileage_km is not None
            and lot.mileage_km is not None
            and row.mileage_km > lot.mileage_km + 1000
        ):
            alerts.append(
                AnomalyAlert(
                    type="odometer_rollback",
                    severity=AnomalySeverity.CRITICAL,
                    title_ru="Скрученный одометр",
                    message_ru=(
                        f"Пробег уменьшился относительно торгов {past_date} "
                        f"({row.mileage_km} км -> {lot.mileage_km} км)"
                    ),
                    diff_details=context,
                )
            )

        past_grade_num = _parse_grade(row.grade)
        if (
            not _is_repaired_grade(row.grade)
            and past_grade_num is not None
            and our_grade_num is not None
            and our_grade_num - past_grade_num >= 0.5
        ):
            alerts.append(
                AnomalyAlert(
                    type="grade_inflation",
                    severity=AnomalySeverity.WARNING,
                    title_ru="Завышение оценки на текущих торгах",
                    message_ru=(
                        f"Оценка {past_grade_num} на {past_house} -> {lot.overall_grade} сейчас. "
                        "Разница 0.5+ балла требует ручной проверки листа"
                    ),
                    diff_details=context,
                )
            )

    return alerts


def _plural_candidates(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return "кандидата"
    return "кандидатов"


def _plural_trades(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return "торга"
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return "торга"
    return "торгов"


def _build_outcome(
    history_rows: list[_VerifiedRow],
    alerts: list[AnomalyAlert],
    *,
    includes_own_lot: bool,
    future_verified_count: int = 0,
    candidates_checked: int = 0,
    now: datetime | None = None,
) -> CrossAuditOutcome:
    """Assemble final CrossAuditOutcome with sorted alerts and sanitized archive history."""
    severity_rank = {
        AnomalySeverity.CRITICAL: 0,
        AnomalySeverity.WARNING: 1,
        AnomalySeverity.INFO: 2,
    }
    alerts.sort(key=lambda a: severity_rank[a.severity])

    has_critical = any(a.severity == AnomalySeverity.CRITICAL for a in alerts)
    has_warning = any(a.severity == AnomalySeverity.WARNING for a in alerts)

    if not history_rows:
        status = CrossAuditStatus.NOT_FOUND
        risk = RiskLevel.INFO
        headline = (
            "Совпадений по номеру кузова в каталоге Aleado не найдено "
            f"(проверено {candidates_checked} "
            f"{_plural_candidates(candidates_checked)})"
        )
    elif has_critical:
        status = CrossAuditStatus.ANOMALY_DETECTED
        risk = RiskLevel.CRITICAL
        headline = alerts[0].title_ru
    elif has_warning:
        status = CrossAuditStatus.LIVE_ONLY
        risk = RiskLevel.WARNING
        headline = "Найдена история торгов; требуется ручная проверка расхождений оценок"
    else:
        status = CrossAuditStatus.LIVE_ONLY
        risk = RiskLevel.INFO
        headline = "История торгов найдена; критичных расхождений оценок и пробега нет"

    if future_verified_count > 0:
        headline += (
            f"; лот присутствует в текущем каталоге Aleado "
            f"({future_verified_count} предстоящих "
            f"{_plural_trades(future_verified_count)})"
        )
    if includes_own_lot:
        headline += "; лот присутствует в текущем каталоге Aleado"

    moment = now or timezone.now()
    history = [
        PastAuctionRecord(
            auction_date=(
                verified.row.trading_date.date() if verified.row.trading_date else moment.date()
            ),
            auction_house=(verified.row.auction_house or "unknown")[:100],
            auction_strictness=None,
            lot_number=(verified.row.lot_number or "?")[:50],
            overall_grade=(verified.row.grade or "-")[:10],
            mileage_km=verified.row.mileage_km,
            defects_summary=None,
            closing_price_jpy=None,
            sheet_archive_url=_safe_archive_url(verified.row.photo_url),
        )
        for verified in history_rows
    ]

    return CrossAuditOutcome(
        status=status,
        risk_level=risk,
        has_critical_anomaly=has_critical,
        headline_ru=headline[:500],
        times_auctioned=len(history_rows),
        is_archive_available=True,
        history=history[:_MAX_HISTORY_ROWS],
        anomalies=alerts,
    )
