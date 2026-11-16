"""Aleado cross-audit service facade: chassis verification and persistence."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx
from django.db import transaction
from django.utils import timezone

from apps.core.enums import CrossAuditStatus, RiskLevel
from apps.integrations.aleado.client import (
    AleadoAuthError,
    AleadoClient,
    AleadoUnavailableError,
)
from apps.integrations.aleado.comparator import (
    SOURCE_NAME,
    CrossAuditOutcome,
    _build_outcome,
    _evaluate_rules,
    _VerifiedRow,
)
from apps.integrations.aleado.matcher import (
    _candidate_is_own_lot,
    _normalize_frame_id,
    clean_model_code,
    select_and_sort_candidates,
)
from apps.integrations.aleado.parser import AleadoParseError
from apps.integrations.ml.client import MlServiceError, MlServiceUnavailableError
from apps.lots.models import AnomalyAlert, CrossAuditReport, Lot, PastAuctionRecord

if TYPE_CHECKING:
    from datetime import datetime

    from apps.integrations.aleado.parser import AleadoLotRow
    from apps.integrations.ml.client import MlServiceClient

logger = logging.getLogger(__name__)

__all__ = [
    "SOURCE_NAME",
    "AleadoCrossAuditService",
    "CrossAuditOutcome",
    "_VerifiedRow",
    "_build_outcome",
    "_candidate_is_own_lot",
    "_evaluate_rules",
    "clean_model_code",
]


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


def _partition_verified_by_time(
    verified_rows: list[_VerifiedRow],
    now: datetime,
) -> tuple[list[_VerifiedRow], int]:
    verified_past: list[_VerifiedRow] = []
    future_verified = 0
    for verified in verified_rows:
        trading_date = verified.row.trading_date
        if trading_date is None:
            continue
        if timezone.is_naive(trading_date):
            trading_date = timezone.make_aware(trading_date)
        if trading_date > now:
            future_verified += 1
        else:
            verified_past.append(verified)
    return verified_past, future_verified


class AleadoCrossAuditService:
    """Cross-audit a lot against the Aleado auction catalog via chassis OCR verification."""

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
        if self.ml_client is not None:
            return self.ml_client
        from django.conf import settings

        from apps.integrations.ml.client import MlServiceClient

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
                rows = self.client.search_lots(model_code, None)
        except AleadoAuthError:
            logger.exception("Aleado authentication failed for lot %s", lot.pk)
            return self._save_unavailable(lot, "Ошибка авторизации в каталоге Aleado")
        except (AleadoUnavailableError, AleadoParseError):
            logger.exception("Aleado is unreachable for lot %s", lot.pk)
            return self._save_unavailable(lot, "Каталог Aleado недоступен")

        candidates, includes_own = select_and_sort_candidates(rows, lot, model_code)
        checked = candidates[: self._verify_candidates_limit]
        verified_rows = self._verify_candidates(lot, checked)

        now = timezone.now()
        verified_past, future_verified = _partition_verified_by_time(verified_rows, now)
        alerts = _evaluate_rules(lot, verified_past)
        outcome = _build_outcome(
            verified_past,
            alerts,
            includes_own_lot=includes_own,
            future_verified_count=future_verified,
            candidates_checked=len(checked),
            now=now,
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
