"""Individual DAG pipeline stages for processing one batch item."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from apps.core.enums import ItemProcessingStatus, TaskStep
from apps.integrations.aleado import AleadoCrossAuditService
from apps.integrations.currency.service import build_currency_service, to_customs_rates_input
from apps.integrations.drom import DromMarketService
from apps.integrations.drom.schemas import DromFetchError, DromMarketResult, DromSearchCriteria
from apps.integrations.farpost.service import save_repair_estimate
from apps.lots.calculator.economics import (
    EV_MISSING_POWER_WARNING,
    _missing_customs_inputs,
    _resolve_start_bid_jpy,
    ensure_dynamic_bid_slider_max,
    ensure_lot_baseline,
    recompute_lot_economics,
)
from apps.lots.calculator.safety import build_cross_audit_baseline, build_safety_checklist
from apps.lots.calculator.scoring import compute_verdict
from apps.lots.lifecycle import compute_lot_expires_at
from apps.lots.models import (
    Batch,
    BatchItem,
    CustomsCalculation,
    Lot,
    MarketComparisonInfo,
    WiseCostLadder,
)
from apps.lots.pipeline.leases import managed_closing, renew_batch_lease

if TYPE_CHECKING:
    import uuid

logger = logging.getLogger(__name__)

_PIPELINE_STEP_DELAY_SEC = 0.0
_EV_MISSING_POWER_WARNING = EV_MISSING_POWER_WARNING

_SUMMARY_REQUIRED_FIELDS: tuple[str, ...] = (
    "make",
    "model",
    "frame_id",
    "auction_house",
    "lot_number",
    "overall_grade",
    "turnkey_cost_rub",
    "market_price_rf_rub",
    "verdict",
    "verdict_headline",
    "net_benefit_rub",
)


def _claim_next_queued_item(batch_id: uuid.UUID) -> BatchItem | None:
    with transaction.atomic():
        item = (
            BatchItem.objects.select_for_update(skip_locked=True)
            .filter(batch_id=batch_id, status=ItemProcessingStatus.QUEUED)
            .order_by("file_index")
            .first()
        )
        if item is None:
            return None
        item.status = ItemProcessingStatus.PROCESSING
        item.current_step = TaskStep.GATEKEEPER
        item.save(update_fields=["status", "current_step", "updated_at"])
        Batch.objects.filter(pk=batch_id).update(updated_at=timezone.now())
        return item


def _is_item_failed(item: BatchItem) -> bool:
    return BatchItem.objects.filter(pk=item.pk, status=ItemProcessingStatus.FAILED).exists()


def _advance_step(item: BatchItem, step: TaskStep) -> None:
    now = timezone.now()
    updated = (
        BatchItem.objects.filter(pk=item.pk)
        .exclude(status=ItemProcessingStatus.FAILED)
        .update(current_step=step, updated_at=now)
    )
    if updated:
        item.current_step = step
        if item.batch_id:
            Batch.objects.filter(pk=item.batch_id).update(updated_at=now)
            renew_batch_lease(item.batch_id)
        if _PIPELINE_STEP_DELAY_SEC > 0:
            time.sleep(_PIPELINE_STEP_DELAY_SEC)


def _fail_item(item: BatchItem, step: TaskStep, message: str) -> None:
    updated = (
        BatchItem.objects.filter(pk=item.pk)
        .exclude(status=ItemProcessingStatus.FAILED)
        .update(
            status=ItemProcessingStatus.FAILED,
            current_step=step,
            error_message=message,
            updated_at=timezone.now(),
        )
    )
    if updated:
        item.status = ItemProcessingStatus.FAILED
        item.current_step = step
        item.error_message = message


def _missing_summary_fields(lot: Lot) -> list[str]:
    missing: list[str] = []
    for name in _SUMMARY_REQUIRED_FIELDS:
        value = getattr(lot, name, None)
        if value is None or value == "":
            missing.append(name)
    return missing


def _complete_item(item: BatchItem) -> None:
    item.status = ItemProcessingStatus.READY
    item.current_step = TaskStep.COMPLETED
    if item.lot is not None:
        now = timezone.now()
        item.lot.completed_at = now
        update_fields = ["completed_at", "updated_at"]
        if item.lot.expires_at is None and not item.lot.auto_archive_disabled:
            item.lot.expires_at = compute_lot_expires_at(
                item.lot.created_at or now,
                item.lot.auction_date,
            )
            update_fields.append("expires_at")
        item.lot.save(update_fields=update_fields)
    item.save(update_fields=["status", "current_step", "updated_at"])


def _step_gatekeeper(item: BatchItem) -> bool:
    _advance_step(item, TaskStep.GATEKEEPER)
    if not item.original_file or not item.original_file.storage.exists(item.original_file.name):
        _fail_item(item, TaskStep.FAILED, "Файл не найден на диске")
        return False
    return True


def _step_cross_audit(item: BatchItem) -> bool:
    _advance_step(item, TaskStep.CROSS_AUDIT)
    lot = item.lot
    if lot is None:
        _fail_item(item, TaskStep.FAILED, "Лот не привязан к элементу пачки")
        return False
    try:
        with managed_closing(AleadoCrossAuditService()) as audit_service:
            audit_service.audit_lot(lot)
    except Exception:
        logger.exception("Aleado cross audit failed for item %s", item.pk)
        try:
            build_cross_audit_baseline(lot)
        except Exception:
            logger.exception("Cross audit baseline failed for item %s", item.pk)
            _fail_item(item, TaskStep.FAILED, "Не удалось зафиксировать результаты кросс-аудита")
            return False
    if _is_item_failed(item):
        return False
    try:
        build_safety_checklist(lot)
    except Exception:
        logger.exception("Safety checklist failed for item %s", item.pk)
        _fail_item(item, TaskStep.FAILED, "Не удалось построить чек-лист систем безопасности")
        return False
    return True


def _persist_drom_market_result(lot: Lot, result: DromMarketResult) -> None:
    with transaction.atomic():
        lot_locked = Lot.objects.select_for_update().get(pk=lot.pk)
        lot_locked.market_price_rf_rub = result.market_price_rf_rub
        update_fields = ["market_price_rf_rub", "updated_at"]
        if lot_locked.power_hp is None and result.power_hp is not None:
            lot_locked.power_hp = result.power_hp
            lot_locked.power_hp_source = result.power_hp_source
            lot_locked.is_under_160_hp = result.is_under_160_hp
            update_fields.extend(["power_hp", "power_hp_source", "is_under_160_hp"])
        lot_locked.save(update_fields=update_fields)

        MarketComparisonInfo.objects.update_or_create(
            lot=lot_locked,
            defaults={
                "market_price_rf_rub": result.market_price_rf_rub,
                "analogs_count": result.analogs_count,
                "price_min_rub": result.price_min_rub,
                "price_max_rub": result.price_max_rub,
                "search_region_ru": result.search_region_ru,
                "excludes_under_order": result.excludes_under_order,
                "filtered_out_under_order_count": result.filtered_out_under_order_count,
                "is_fallback": result.is_fallback,
                "fallback_reason_ru": result.fallback_reason_ru,
                "drom_search_url": result.drom_search_url,
            },
        )


def _step_drom_market(item: BatchItem) -> bool:
    try:
        lot = item.lot
        if lot is None or not lot.make or not lot.model:
            _fail_item(item, TaskStep.FAILED, "Недостаточно данных для поиска аналогов на Drom.ru")
            return False

        criteria = DromSearchCriteria(
            make=lot.make,
            model=lot.model,
            year=lot.year or lot.first_reg_year,
            engine_cc=lot.engine_cc,
            drive_type=lot.drive_type,
            transmission=lot.transmission,
            fuel_type=lot.fuel_type,
            model_code=lot.model_code,
            trim=lot.trim,
        )
        result = DromMarketService().evaluate(criteria)
        if _is_item_failed(item):
            return False
        _persist_drom_market_result(lot, result)
        return True
    except DromFetchError as exc:
        logger.warning("Drom market step failed for item %s: %s", item.pk, exc)
        _fail_item(item, TaskStep.FAILED, "Не удалось получить рыночные аналоги на Drom.ru")
        return False
    except Exception:
        logger.exception("Unexpected error in Drom market step for item %s", item.pk)
        _fail_item(item, TaskStep.FAILED, "Ошибка при подборе рыночных аналогов на Drom.ru")
        return False


def _step_farpost_parts(item: BatchItem) -> bool:
    if item.lot is None:
        _fail_item(item, TaskStep.FAILED, "Лот не привязан к элементу пачки")
        return False
    if _is_item_failed(item):
        return False
    try:
        save_repair_estimate(item.lot)
    except Exception:
        logger.exception("Repair estimate failed for item %s", item.pk)
        _fail_item(item, TaskStep.FAILED, "Не удалось сформировать смету ремонта")
        return False
    return True


def _ensure_lot_rates(lot: Lot) -> bool:
    if lot.customs_rates_input or (
        CustomsCalculation.objects.filter(lot=lot, rates_snapshot__isnull=False).exists()
    ):
        return True
    try:
        result = build_currency_service().get_currency_rates()
    except Exception:
        logger.exception("Currency rates gateway failed for lot %s", lot.pk)
        return False
    lot.customs_rates_input = to_customs_rates_input(result)
    lot.save(update_fields=["customs_rates_input", "updated_at"])
    logger.info(
        "Rates attached to lot %s: origin=%s cbrf_date=%s",
        lot.pk,
        result.origin.value,
        result.cbrf_date,
    )
    return True


def _step_customs_calc(item: BatchItem) -> bool:
    _advance_step(item, TaskStep.CUSTOMS_CALC)
    lot = item.lot
    if lot is None:
        _fail_item(item, TaskStep.FAILED, "Лот не привязан к элементу пачки")
        return False
    lot.refresh_from_db()
    if not _ensure_lot_rates(lot):
        _fail_item(item, TaskStep.FAILED, "Не удалось получить курсы валют (шлюз ЦБ РФ)")
        return False
    ensure_dynamic_bid_slider_max(lot)
    try:
        ladder = WiseCostLadder.objects.filter(lot=lot).first()
        bid_jpy = ladder.car_bid_jpy if ladder is not None else _resolve_start_bid_jpy(lot)
    except Exception:
        logger.exception("Start bid derivation failed for lot %s", lot.pk)
        _fail_item(item, TaskStep.FAILED, "Не удалось определить стартовую ставку лота")
        return False
    missing = _missing_customs_inputs(lot, bid_jpy)
    if missing:
        _fail_item(
            item,
            TaskStep.FAILED,
            "Недостаточно данных для расчёта таможни: " + ", ".join(missing),
        )
        return False
    try:
        recompute_lot_economics(lot, bid_jpy=bid_jpy)
        lot.refresh_from_db()
        customs_model = CustomsCalculation.objects.filter(lot=lot).first()
        ladder_model = WiseCostLadder.objects.filter(lot=lot).first()
        if customs_model is not None and ladder_model is not None:
            ensure_lot_baseline(lot, customs_model, ladder_model)
    except Exception:
        logger.exception("Customs recomputation failed for lot %s", lot.pk)
        _fail_item(item, TaskStep.FAILED, "Не удалось рассчитать таможные платежи")
        return False
    return True


def _step_scoring(item: BatchItem) -> bool:
    _advance_step(item, TaskStep.SCORING)
    lot = item.lot
    if lot is None:
        _fail_item(item, TaskStep.FAILED, "Лот не привязан к элементу пачки")
        return False
    lot.refresh_from_db()
    try:
        compute_verdict(lot)
    except Exception:
        logger.exception("Scoring failed for lot %s", lot.pk)
        _fail_item(item, TaskStep.FAILED, "Не удалось рассчитать вердикт светофора")
        return False
    return True
