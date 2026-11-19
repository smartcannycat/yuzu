"""Transactional recalculation and baseline-reset orchestration (API-free)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from apps.core.math_utils import round_half_up_int, to_decimal
from apps.lots.calculator.baseline import (
    MAX_DYNAMIC_BID_SLIDER_MAX_JPY,
    ensure_lot_baseline,
    extract_rates,
    is_simulation_modified,
)
from apps.lots.calculator.economics import recompute_lot_economics
from apps.lots.calculator.scoring import compute_verdict
from apps.lots.exceptions import LotNotFoundDomainError, RecalcDomainError
from apps.lots.models import (
    CustomsCalculation,
    Lot,
    TrafficLightVerdict,
    WiseCostLadder,
)

if TYPE_CHECKING:
    from datetime import datetime

    from apps.users.models import User


@dataclass(frozen=True)
class RecalcOutcome:
    """Domain result returned after transactional lot recalculation or baseline reset."""

    lot: Lot
    customs: CustomsCalculation
    ladder: WiseCostLadder
    verdict: TrafficLightVerdict
    applied_bid_rub: int
    is_simulation_modified: bool
    pdf_report_stale: bool
    recalculated_at: datetime


def _get_ready_user_lot(user: User, lot_id) -> Lot:
    lot = Lot.objects.ready_for_user(user).select_for_update().filter(pk=lot_id).first()
    if lot is None:
        raise LotNotFoundDomainError("Лот не найден", title="Лот не найден")
    return lot


def _load_recalc_outcome(
    lot: Lot,
    *,
    verdict: TrafficLightVerdict,
    pdf_report_stale: bool,
) -> RecalcOutcome:
    lot.refresh_from_db()
    customs_model = CustomsCalculation.objects.select_related("rates_snapshot").get(lot=lot)
    ladder = WiseCostLadder.objects.select_related("lot").get(lot=lot)
    rates_model = customs_model.rates_snapshot
    applied_bid_rub = round_half_up_int(ladder.car_bid_jpy, rates_model.jpy_rub_bank)
    return RecalcOutcome(
        lot=lot,
        customs=customs_model,
        ladder=ladder,
        verdict=verdict,
        applied_bid_rub=applied_bid_rub,
        is_simulation_modified=is_simulation_modified(lot, customs_model, ladder),
        pdf_report_stale=pdf_report_stale,
        recalculated_at=timezone.now(),
    )


def _resolve_bid_jpy_from_rub(
    lot: Lot,
    customs_model: CustomsCalculation | None,
    bid_rub: int,
) -> int:
    rates_data, _ = extract_rates(lot, customs_model)
    if rates_data is None:
        raise RecalcDomainError(
            "Для пересчёта по ставке в рублях требуется снимок курсов валют",
            title="Курсы валют недоступны",
        )
    if not math.isfinite(rates_data.jpy_rub_bank) or rates_data.jpy_rub_bank <= 0:
        raise RecalcDomainError(
            "Некорректный курс JPY/RUB в снимке курсов",
            title="Курсы валют недоступны",
        )
    resolved_bid_jpy = round_half_up_int(to_decimal(bid_rub) / to_decimal(rates_data.jpy_rub_bank))
    if resolved_bid_jpy < 100_000:
        raise RecalcDomainError(
            "Ставка в йенах не может быть меньше 100 000 ¥",
            title="Некорректная ставка",
        )
    if resolved_bid_jpy > MAX_DYNAMIC_BID_SLIDER_MAX_JPY:
        raise RecalcDomainError(
            f"Ставка в йенах не может превышать {MAX_DYNAMIC_BID_SLIDER_MAX_JPY:,} ¥".replace(
                ",", " "
            ),
            title="Некорректная ставка",
        )
    return resolved_bid_jpy


@transaction.atomic
def execute_recalculate(
    user: User,
    lot_id,
    *,
    bid_jpy: int | None = None,
    bid_rub: int | None = None,
    is_commercial_util: bool | None = None,
    include_repairs: bool | None = None,
    custom_power_hp: int | None = None,
    custom_freight_rub: int | None = None,
) -> RecalcOutcome:
    lot = _get_ready_user_lot(user, lot_id)
    customs_model = CustomsCalculation.objects.filter(lot=lot).first()
    ladder_model = WiseCostLadder.objects.filter(lot=lot).first()
    if customs_model is not None and ladder_model is not None:
        ensure_lot_baseline(lot, customs_model, ladder_model)

    resolved_bid_jpy = bid_jpy
    if resolved_bid_jpy is None and bid_rub is not None:
        resolved_bid_jpy = _resolve_bid_jpy_from_rub(lot, customs_model, bid_rub)

    try:
        recompute_lot_economics(
            lot,
            bid_jpy=resolved_bid_jpy,
            is_commercial_util=is_commercial_util,
            include_repairs=include_repairs,
            custom_power_hp=custom_power_hp,
            custom_freight_rub=custom_freight_rub,
        )
    except ValueError as exc:
        raise RecalcDomainError(
            str(exc),
            title="Недостаточно данных для расчёта",
        ) from exc

    lot.refresh_from_db()
    verdict = compute_verdict(lot)
    return _load_recalc_outcome(lot, verdict=verdict, pdf_report_stale=True)


@transaction.atomic
def execute_reset_simulation(user: User, lot_id) -> RecalcOutcome:
    """Restore the lot's persisted economics to its captured initial baseline."""
    lot = _get_ready_user_lot(user, lot_id)
    customs_model = CustomsCalculation.objects.filter(lot=lot).first()
    ladder_model = WiseCostLadder.objects.filter(lot=lot).first()
    if customs_model is None or ladder_model is None:
        raise RecalcDomainError(
            "Отсутствует базовый расчёт экономики лота",
            title="Недостаточно данных для расчёта",
        )

    baseline = ensure_lot_baseline(lot, customs_model, ladder_model)
    base_power_hp = baseline.get("power_hp")
    lot.power_hp = base_power_hp
    lot.power_hp_source = baseline.get("power_hp_source")
    lot.is_under_160_hp = base_power_hp <= 160 if base_power_hp is not None else None
    lot.save(update_fields=["power_hp", "power_hp_source", "is_under_160_hp", "updated_at"])

    freight_base = baseline.get("freight_rub")
    try:
        recompute_lot_economics(
            lot,
            bid_jpy=int(baseline["bid_jpy"]),
            is_commercial_util=bool(baseline.get("is_commercial_util", False)),
            include_repairs=bool(baseline.get("include_repairs", True)),
            custom_freight_rub=int(freight_base) if freight_base is not None else None,
        )
    except ValueError as exc:
        raise RecalcDomainError(
            str(exc),
            title="Недостаточно данных для расчёта",
        ) from exc

    lot.refresh_from_db()
    verdict = compute_verdict(lot)
    return _load_recalc_outcome(lot, verdict=verdict, pdf_report_stale=False)
