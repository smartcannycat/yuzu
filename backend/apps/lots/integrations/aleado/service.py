"""Aleado cross-audit service: trading history, anomaly rules and reports.

The search over the same model type code (body code) plus the
registration year returns ALL cars of that body/year - different
physical vehicles. Candidate rows are therefore verified by chassis
number: the lot detail page carries a small chassis-number image, which
is read via the ML service (Gemini OCR) and compared with the audited
lot's ``frame_id``. Only verified matches reach trading history and the
anomaly rules, which eliminates false ``odometer_rollback`` firings on
unrelated cars of the same body.

Verified rows are split by trading date: rows at or before now are
history (rules apply), rows in the future are the current catalog
presence and are reported in the headline only.

Status mapping (CrossAuditStatus):
- ``anomaly_detected`` - at least one CRITICAL anomaly rule fired on a
  verified past row.
- ``live_only``        - verified past history exists but only
  WARNING/INFO findings.
- ``not_found``        - no verified past rows (unverified candidates do
  not count as history).
- ``unavailable``      - Aleado did not return a usable search page.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import httpx
from django.db import transaction
from django.utils import timezone

from apps.core.enums import AnomalySeverity, CrossAuditStatus, RiskLevel
from apps.lots.integrations.aleado.client import (
    AleadoAuthError,
    AleadoClient,
    AleadoUnavailableError,
)
from apps.lots.integrations.aleado.parser import AleadoParseError
from apps.lots.integrations.ml.client import (
    MlServiceError,
    MlServiceUnavailableError,
)
from apps.lots.models import AnomalyAlert, CrossAuditReport, Lot, PastAuctionRecord

if TYPE_CHECKING:
    from apps.lots.integrations.aleado.parser import AleadoLotDetail, AleadoLotRow
    from apps.lots.integrations.ml.client import MlServiceClient

logger = logging.getLogger(__name__)

SOURCE_NAME = "Aleado.com"

# Grades that mark repaired/damaged vehicles on Japanese auction sheets.
_REPAIRED_GRADES = frozenset({"R", "RA", "0"})
_NUMERIC_GRADE_RE = re.compile(r"^\d(\.\d)?$")

# A past row whose lot number and auction house match the current lot is
# the lot itself (listed for upcoming trading), not history.
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


def clean_model_code(lot: Lot) -> str:
    """Derive the Aleado model type code from the lot's frame/model code.

    Strips emission prefixes ("6BA-GB5" -> "GB5", "DAA-RU3" -> "RU3").
    A Frame ID ("GB5-1025108") contributes the part before the dash.
    """
    for value in (lot.frame_id, lot.model_code):
        code = (value or "").upper().strip()
        if not code:
            continue
        parts = code.split("-")
        if len(parts) >= 2 and re.fullmatch(r"[A-Z]{2,}\d{1,4}[A-Z]?", parts[-1]):
            # Emission-prefixed model code (6BA-GB5) or full frame ID.
            return parts[-1]
        if re.fullmatch(r"[A-Z]{2,}\d{1,4}[A-Z]?", parts[0]):
            return parts[0]
    return ""


def _parse_grade(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _is_repaired_grade(value: str | None) -> bool:
    return (value or "").upper().strip() in _REPAIRED_GRADES


def _format_date(value: Any) -> str:
    return value.strftime("%d.%m.%Y") if value is not None else "-"


def _candidate_is_own_lot(row: AleadoLotRow, lot: Lot) -> bool:
    own_lot_number = (lot.lot_number or "").strip()
    if not own_lot_number or not row.lot_number:
        return False
    if row.lot_number.strip() != own_lot_number:
        return False
    own_house = (lot.auction_house or "").upper()
    branch = (lot.auction_branch or "").upper()
    house = row.auction_house.upper()
    return branch in house or house.startswith(own_house) or own_house in house


def _normalize_frame_id(value: str | None) -> str:
    """Normalize a frame id for comparison: uppercase, no internal spaces."""
    return re.sub(r"\s+", "", (value or "").strip().upper())


@dataclass(frozen=True)
class _VerifiedRow:
    """A candidate row whose chassis number matched the audited lot."""

    row: AleadoLotRow
    detail: AleadoLotDetail | None = None


def _evaluate_rules(lot: Lot, rows: list[_VerifiedRow]) -> list[AnomalyAlert]:
    """Apply the planning/01 anomaly cascade to verified past rows."""
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
            continue

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
            continue

        past_grade_num = _parse_grade(row.grade)
        if (
            past_grade_num is not None
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


def _safe_archive_url(photo_url: str | None) -> str | None:
    """Allowlist-check a photo URL scraped from Aleado markup.

    The value comes from untrusted HTML and is later exposed through the
    API; anything outside https + aleado image hosts (including
    ``javascript:`` URIs) is dropped rather than persisted.
    """
    if not photo_url:
        return None
    parsed = urlparse(photo_url)
    if parsed.scheme == "https" and parsed.hostname in {
        "p3.aleado.com",
        "auc.aleado.com",
    }:
        return photo_url[:500]
    return None


def _build_outcome(
    history_rows: list[_VerifiedRow],
    alerts: list[AnomalyAlert],
    *,
    includes_own_lot: bool,
    future_verified_count: int = 0,
    candidates_checked: int = 0,
) -> CrossAuditOutcome:
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
        top = alerts[0]
        headline = top.title_ru
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

    history: list[PastAuctionRecord] = []
    for verified in history_rows:
        row = verified.row
        history.append(
            PastAuctionRecord(
                auction_date=row.trading_date.date() if row.trading_date else timezone.now().date(),
                auction_house=(row.auction_house or "unknown")[:100],
                auction_strictness=None,
                lot_number=(row.lot_number or "?")[:50],
                overall_grade=(row.grade or "-")[:10],
                mileage_km=row.mileage_km,
                defects_summary=None,
                closing_price_jpy=row.start_price_jpy,
                sheet_archive_url=_safe_archive_url(row.photo_url),
            )
        )

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


def _persist(lot: Lot, outcome: CrossAuditOutcome) -> CrossAuditReport:
    with transaction.atomic():
        report = CrossAuditReport.objects.update_or_create(
            lot=lot,
            defaults={
                "status": outcome.status,
                "source_name": outcome.source_name,
                "is_archive_available": outcome.is_archive_available,
                "risk_level": outcome.risk_level,
                "has_critical_anomaly": outcome.has_critical_anomaly,
                "headline_ru": outcome.headline_ru,
                "times_auctioned": outcome.times_auctioned,
                "verified_at": timezone.now(),
            },
        )[0]

        report.history.all().delete()
        PastAuctionRecord.objects.bulk_create(
            PastAuctionRecord(
                audit=report,
                auction_date=record.auction_date,
                auction_house=record.auction_house,
                auction_strictness=record.auction_strictness,
                lot_number=record.lot_number,
                overall_grade=record.overall_grade,
                mileage_km=record.mileage_km,
                defects_summary=record.defects_summary,
                closing_price_jpy=record.closing_price_jpy,
                sheet_archive_url=record.sheet_archive_url,
            )
            for record in outcome.history
        )
        report.anomalies.all().delete()
        AnomalyAlert.objects.bulk_create(
            AnomalyAlert(
                audit=report,
                type=alert.type,
                severity=alert.severity,
                title_ru=alert.title_ru,
                message_ru=alert.message_ru,
                diff_details=alert.diff_details,
            )
            for alert in outcome.anomalies
        )

        has_anomaly = outcome.has_critical_anomaly
        lot.has_anomaly = has_anomaly
        lot.anomaly_text = (
            outcome.anomalies[0].message_ru[:500] if has_anomaly and outcome.anomalies else None
        )
        lot.save(update_fields=["has_anomaly", "anomaly_text", "updated_at"])
    return report


class AleadoCrossAuditService:
    """Cross-audit a lot against the Aleado auction catalog.

    Candidates found by model code + year are different physical cars;
    each candidate is verified by chassis number OCR (via the ML
    service) before it can enter trading history or anomaly rules.
    """

    def __init__(
        self,
        client: AleadoClient | None = None,
        ml_client: MlServiceClient | None = None,
    ) -> None:
        if client is None:
            from django.conf import settings

            client = AleadoClient(
                base_url=settings.ALEADO_BASE_URL,
                username=settings.ALEADO_USERNAME,
                password=settings.ALEADO_PASSWORD,
                timeout_sec=settings.ALEADO_TIMEOUT_SEC,
                request_interval_sec=settings.ALEADO_REQUEST_INTERVAL_SEC,
            )
        self.client = client
        self.ml_client = ml_client
        self._verify_candidates_limit = self._resolve_verify_limit()

    @staticmethod
    def _resolve_verify_limit() -> int:
        from django.conf import settings

        return max(0, int(getattr(settings, "ALEADO_VERIFY_CANDIDATES", 10)))

    def _get_ml_client(self) -> MlServiceClient | None:
        """Return the injected ML client or build one from Django settings."""
        if self.ml_client is not None:
            return self.ml_client
        from django.conf import settings

        from apps.lots.integrations.ml.client import MlServiceClient

        self.ml_client = MlServiceClient(
            base_url=settings.ML_SERVICE_URL,
            timeout_sec=settings.ML_SERVICE_TIMEOUT_SEC,
            api_key=settings.ML_SERVICE_API_KEY,
        )
        return self.ml_client

    def audit_lot(self, lot: Lot) -> CrossAuditOutcome:
        """Run the full audit flow for one lot and persist the report."""
        model_code = clean_model_code(lot)
        if not model_code:
            logger.warning("Aleado audit skipped: no model code for lot %s", lot.pk)
            return self._save_unavailable(lot, "Не удалось определить код кузова для поиска")

        try:
            rows = self.client.search_lots(model_code, lot.first_reg_year)
            if not rows and lot.first_reg_year is not None:
                # Wider retry: same body code, any production year.
                rows = self.client.search_lots(model_code, None)
        except AleadoAuthError:
            logger.exception("Aleado authentication failed for lot %s", lot.pk)
            return self._save_unavailable(lot, "Ошибка авторизации в каталоге Aleado")
        except (AleadoUnavailableError, AleadoParseError):
            logger.exception("Aleado is unreachable for lot %s", lot.pk)
            return self._save_unavailable(lot, "Каталог Aleado недоступен")

        candidates: list[AleadoLotRow] = []
        includes_own = False
        for row in rows:
            if row.model_type and row.model_type.upper() != model_code:
                continue
            if _candidate_is_own_lot(row, lot):
                includes_own = True
                continue
            candidates.append(row)

        # Closest mileage first: real same-car matches tend to sit near
        # the audited mileage, so verification finds them early. None
        # mileage goes last. No early stop: every verified match is
        # history, not just the first one.
        candidates.sort(
            key=lambda r: (
                r.mileage_km is None,
                abs(r.mileage_km - lot.mileage_km)
                if r.mileage_km is not None and lot.mileage_km is not None
                else 0,
            )
        )

        verified_rows = self._verify_candidates(lot, candidates[: self._verify_candidates_limit])

        now = timezone.now()
        verified_past: list[_VerifiedRow] = []
        future_verified = 0
        for verified in verified_rows:
            trading_date = verified.row.trading_date
            if trading_date is not None and timezone.is_naive(trading_date):
                trading_date = timezone.make_aware(trading_date)
            if trading_date is not None and trading_date > now:
                future_verified += 1
            else:
                verified_past.append(verified)

        alerts = _evaluate_rules(lot, verified_past)
        outcome = _build_outcome(
            verified_past,
            alerts,
            includes_own_lot=includes_own,
            future_verified_count=future_verified,
            candidates_checked=len(candidates[: self._verify_candidates_limit]),
        )
        _persist(lot, outcome)
        logger.info(
            "Aleado cross-audit for lot %s: candidates=%d verified=%d past=%d future=%d status=%s",
            lot.pk,
            len(candidates),
            len(verified_rows),
            len(verified_past),
            future_verified,
            outcome.status,
        )
        return outcome

    def _verify_candidates(self, lot: Lot, candidates: list[AleadoLotRow]) -> list[_VerifiedRow]:
        """Verify candidates by chassis number; errors keep them unverified."""
        if not candidates:
            return []
        expected = _normalize_frame_id(lot.frame_id)
        if not expected:
            logger.info(
                "Aleado cross-audit for lot %s: no frame_id, chassis verification impossible",
                lot.pk,
            )
            return []

        ml_client = self._get_ml_client()
        if ml_client is None:
            return []

        verified: list[_VerifiedRow] = []
        for candidate in candidates:
            try:
                verified_row = self._verify_one(candidate, expected, ml_client)
            except (
                AleadoParseError,
                AleadoUnavailableError,
                MlServiceError,
                MlServiceUnavailableError,
                ValueError,
                httpx.HTTPError,
            ) as exc:
                logger.warning(
                    "Aleado chassis verification failed for candidate %s (lot %s): %s",
                    candidate.internal_id,
                    lot.pk,
                    exc,
                )
                continue
            if verified_row is not None:
                verified.append(verified_row)
        return verified

    def _verify_one(
        self,
        candidate: AleadoLotRow,
        expected_frame_id: str,
        ml_client: MlServiceClient,
    ) -> _VerifiedRow | None:
        """Verify one candidate; return None when the chassis does not match."""
        if not candidate.internal_id:
            return None

        detail = self.client.get_lot_detail(candidate.internal_id)
        if not detail.chassis_image_url:
            return None

        image_bytes = self.client.fetch_chassis_image(detail)
        chassis_read = ml_client.read_chassis(image_bytes)
        if chassis_read is None or not chassis_read.frame_id:
            return None

        if _normalize_frame_id(chassis_read.frame_id) != expected_frame_id:
            return None
        return _VerifiedRow(candidate, detail)

    def _save_unavailable(self, lot: Lot, reason_ru: str) -> CrossAuditOutcome:
        outcome = CrossAuditOutcome(
            status=CrossAuditStatus.UNAVAILABLE,
            risk_level=RiskLevel.INFO,
            has_critical_anomaly=False,
            headline_ru=reason_ru,
            times_auctioned=0,
            is_archive_available=False,
        )
        _persist(lot, outcome)
        return outcome
