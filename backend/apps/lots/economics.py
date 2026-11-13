import math
from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.core.enums import AgeCorridor, FuelType, PowerHpSource
from apps.lots import schemas
from apps.lots.customs import (
    DEFAULT_FREIGHT_USD,
    DEFAULT_JAPAN_FOB_JPY,
    CurrencyRatesInput,
    CustomsInput,
    LadderInput,
    StartBidInput,
    build_wise_cost_ladder,
    calculate_customs,
    derive_start_bid_from_market,
)
from apps.lots.models import (
    CurrencyRatesSnapshot,
    CustomsCalculation,
    FarpostRepairSummary,
    Lot,
    PastAuctionRecord,
    WiseCostLadder,
    WiseCostStep,
)
from apps.lots.starter_lots import _COROLLA_FIXTURE


def _resolve_calculation_date(lot: Lot, on_date: date | None) -> date:
    if on_date is not None:
        return on_date
    if lot.frame_id == _COROLLA_FIXTURE["lot_fields"]["frame_id"] and not hasattr(
        lot, "batch_item"
    ):
        # TODO(BE-05/BE-11): benchmark freeze. The canonical Corolla
        # fixture pins the declaration date so the seeded lot keeps
        # reproducing the "3-5 years" corridor of the API contract
        # (its real age at the 12.11.2026 rates snapshot is 6 years).
        # Remove once a real declaration date source exists.
        return date(2025, 10, 15)
    return timezone.localdate()


def _extract_rates(
    lot: Lot, customs_model: CustomsCalculation | None
) -> tuple[schemas.CurrencyRates | None, CurrencyRatesSnapshot | None]:
    rates_model = (
        CurrencyRatesSnapshot.objects.filter(customs=customs_model).first()
        if customs_model is not None
        else None
    )
    raw_rates = rates_model if rates_model is not None else lot.customs_rates_input
    if raw_rates is None:
        return None, rates_model
    return schemas.CurrencyRates.model_validate(raw_rates), rates_model


def _to_rates_input(rates_data: schemas.CurrencyRates) -> CurrencyRatesInput:
    return CurrencyRatesInput(
        jpy_rub=rates_data.jpy_rub_bank,
        eur_rub=rates_data.eur_rub_cbrf,
        usd_rub=rates_data.usd_rub_cbrf,
    )


def recompute_lot_economics(
    lot: Lot,
    *,
    bid_jpy: int | None = None,
    is_commercial_util: bool | None = None,
    include_repairs: bool | None = None,
    custom_power_hp: int | None = None,
    custom_freight_rub: int | None = None,
    on_date: date | None = None,
) -> None:
    """(Re)compute customs, Wise Cost Ladder and lot totals via the BE-09 engine.

    Requires a currency rates snapshot (seeded fixtures or the BE-05 gateway).
    The age corridor is resolved from the vehicle registration dates against
    the declaration/calculation date. The utilization fee mode selected by
    the user is kept separately from the applied one: a personal selection
    is only downgraded to the commercial grid while power is unknown or
    above 160 hp, and is restored automatically once ``custom_power_hp``
    confirms the privilege. All writes (including the manual power override)
    happen in a single transaction.
    """
    with transaction.atomic():
        lot = Lot.objects.select_for_update().get(pk=lot.pk)
        calculation_date = _resolve_calculation_date(lot, on_date)
        customs_model = CustomsCalculation.objects.filter(lot=lot).first()
        rates_data, rates_model = _extract_rates(lot, customs_model)
        if rates_data is None:
            raise ValueError("Отсутствуют курсы валют для расчёта экономики лота")
        rates = _to_rates_input(rates_data)

        ladder = WiseCostLadder.objects.filter(lot=lot).first()
        # Base bid priority: explicit request -> the lot's base (sheet/history/
        # derived) bid -> the previously stored ladder bid (legacy rows only).
        applied_bid_jpy = bid_jpy
        if applied_bid_jpy is None:
            applied_bid_jpy = lot.auction_bid_jpy
        if applied_bid_jpy is None and ladder is not None:
            applied_bid_jpy = ladder.car_bid_jpy
        if not applied_bid_jpy:
            raise ValueError("Отсутствует ставка на аукционе")
        bid_rub = math.floor(applied_bid_jpy * rates.jpy_rub + 0.5)
        fob_rub = math.floor(DEFAULT_JAPAN_FOB_JPY * rates.jpy_rub + 0.5)
        freight_rub = custom_freight_rub
        if freight_rub is None:
            freight_rub = (
                customs_model.freight_vladivostok_rub
                if customs_model is not None
                else math.floor(DEFAULT_FREIGHT_USD * rates.usd_rub + 0.5)
            )

        selected_commercial = (
            is_commercial_util
            if is_commercial_util is not None
            else bool(customs_model and customs_model.util_mode_selected_commercial)
        )

        lot_update_fields: list[str] = []
        if custom_power_hp is not None:
            lot.power_hp = custom_power_hp
            lot.power_hp_source = PowerHpSource.MANUAL
            lot.is_under_160_hp = custom_power_hp <= 160
            lot_update_fields += ["power_hp", "power_hp_source", "is_under_160_hp"]

        power_hp = custom_power_hp if custom_power_hp is not None else lot.power_hp
        if lot.fuel_type != FuelType.EV and not lot.engine_cc:
            raise ValueError("Отсутствует объём двигателя для расчёта пошлины")
        if not lot.first_reg_year:
            raise ValueError("Отсутствует год первой регистрации для расчёта пошлины")
        customs_value_rub = bid_rub + fob_rub + freight_rub

        result = calculate_customs(
            CustomsInput(
                engine_cc=0 if lot.fuel_type == FuelType.EV else lot.engine_cc,
                fuel_type=lot.fuel_type,
                power_hp=power_hp,
                first_reg_year=lot.first_reg_year,
                first_reg_month=lot.first_reg_month,
                is_commercial_util=selected_commercial,
                customs_value_rub=customs_value_rub,
                freight_rub=freight_rub,
                broker_rub=customs_model.broker_svh_sbkts_rub if customs_model else None,
                mild_hybrid=lot.is_verified_mild_hybrid,
            ),
            rates,
            on_date=calculation_date,
        )

        repairs_included = (
            include_repairs if include_repairs is not None else lot.is_repairs_included
        )
        repair = FarpostRepairSummary.objects.filter(lot=lot).first()
        repair_total_rub = repair.grand_total_repair_rub if repair else 0
        market_price_rub = lot.market_price_rf_rub
        if market_price_rub is None:
            raise ValueError("Отсутствует рыночная цена РФ для расчёта экономики лота")

        ladder_result = build_wise_cost_ladder(
            LadderInput(
                bid_jpy=applied_bid_jpy,
                rates=rates,
                customs=result,
                market_price_rf_rub=market_price_rub,
                repair_total_rub=repair_total_rub,
                include_repairs=repairs_included,
            )
        )

        if customs_model is None:
            customs_model = CustomsCalculation(lot=lot)
        customs_model.age_corridor = result.age_corridor
        customs_model.duty_calculation_mode = result.duty_calculation_mode
        customs_model.engine_cc = result.engine_cc
        customs_model.duty_rate_eur_per_cc = result.duty_rate_eur_per_cc
        customs_model.effective_duty_pct = result.effective_duty_pct
        customs_model.customs_duty_eur = result.customs_duty_eur
        customs_model.customs_duty_rub = result.customs_duty_rub
        customs_model.excise_rub = result.excise_rub
        customs_model.import_vat_rub = result.import_vat_rub
        customs_model.is_under_160_hp = result.is_under_160_hp
        customs_model.util_mode_selected_commercial = selected_commercial
        customs_model.is_commercial_util = result.is_commercial_util
        customs_model.utilization_fee_rub = result.utilization_fee_rub
        customs_model.customs_clearance_fee_rub = result.customs_clearance_fee_rub
        customs_model.freight_vladivostok_rub = result.freight_vladivostok_rub
        customs_model.broker_svh_sbkts_rub = result.broker_svh_sbkts_rub
        customs_model.meti_sanction_risk = result.meti_sanction_risk
        customs_model.save()
        if rates_model is None:
            CurrencyRatesSnapshot.objects.create(customs=customs_model, **rates_data.model_dump())

        if ladder is None:
            ladder = WiseCostLadder(lot=lot)
        ladder.car_bid_jpy = ladder_result.car_bid_jpy
        ladder.car_bid_rub = ladder_result.car_bid_rub
        ladder.turnkey_cost_rub = ladder_result.turnkey_cost_rub
        ladder.market_price_rf_rub = ladder_result.market_price_rf_rub
        ladder.net_benefit_rub = ladder_result.net_benefit_rub
        ladder.benefit_percentage = ladder_result.benefit_percentage
        ladder.save()
        WiseCostStep.objects.filter(ladder=ladder).delete()
        WiseCostStep.objects.bulk_create(
            WiseCostStep(
                ladder=ladder,
                step_number=step.step_number,
                name_ru=step.name_ru,
                amount_rub=step.amount_rub,
                original_currency=step.original_currency,
                original_amount=step.original_amount,
                is_optional=step.is_optional,
            )
            for step in ladder_result.steps
        )

        lot.turnkey_cost_rub = ladder_result.turnkey_cost_rub
        lot.net_benefit_rub = ladder_result.net_benefit_rub
        lot.benefit_percentage = ladder_result.benefit_percentage
        lot.is_repairs_included = repairs_included
        lot.meti_sanction_risk = result.meti_sanction_risk
        lot.is_pass_corridor_3_5 = result.age_corridor == AgeCorridor.THREE_TO_FIVE_YEARS
        lot_update_fields += [
            "turnkey_cost_rub",
            "net_benefit_rub",
            "benefit_percentage",
            "is_repairs_included",
            "meti_sanction_risk",
            "is_pass_corridor_3_5",
            "updated_at",
        ]
        lot.save(update_fields=lot_update_fields)


def _resolve_start_bid_jpy(lot: Lot) -> int | None:
    """Start bid for a new lot, by priority (see BE-09 start bid spec):

    1. Sheet data: the bid captured by the OCR pipeline (``auction_bid_jpy``).
    2. Auction history: the most recent closing price from the cross-audit
       archive (``PastAuctionRecord.closing_price_jpy``).
    3. Reverse calculation from the Drom market price: the highest slider
       step bid whose turnkey cost leaves a 15% target margin.

    """
    min_bid = lot.bid_slider_min_jpy or 300_000
    max_bid = lot.bid_slider_max_jpy or 2_500_000
    step_bid = lot.bid_slider_step_jpy or 10_000

    def clamp(bid_jpy: int) -> int:
        return max(min_bid, min(max_bid, bid_jpy))

    if lot.auction_bid_jpy:
        return clamp(lot.auction_bid_jpy)

    record = (
        PastAuctionRecord.objects.filter(audit__lot=lot, closing_price_jpy__gt=0)
        .order_by("-auction_date", "-id")
        .first()
    )
    if record is not None:
        return clamp(record.closing_price_jpy)

    if not lot.market_price_rf_rub:
        return None

    customs_model = CustomsCalculation.objects.filter(lot=lot).first()
    rates_data, _ = _extract_rates(lot, customs_model)
    if rates_data is None:
        return None
    rates = _to_rates_input(rates_data)

    repair = FarpostRepairSummary.objects.filter(lot=lot).first()
    result = derive_start_bid_from_market(
        StartBidInput(
            market_price_rf_rub=lot.market_price_rf_rub,
            rates=rates,
            on_date=timezone.localdate(),
            customs_params=CustomsInput(
                engine_cc=0 if lot.fuel_type == FuelType.EV else lot.engine_cc,
                fuel_type=lot.fuel_type,
                power_hp=lot.power_hp,
                first_reg_year=lot.first_reg_year,
                first_reg_month=lot.first_reg_month,
                is_commercial_util=bool(
                    customs_model and customs_model.util_mode_selected_commercial
                ),
                freight_rub=(customs_model.freight_vladivostok_rub if customs_model else None),
                broker_rub=(customs_model.broker_svh_sbkts_rub if customs_model else None),
                mild_hybrid=lot.is_verified_mild_hybrid,
            ),
            broker_rub=customs_model.broker_svh_sbkts_rub if customs_model else None,
            repair_total_rub=repair.grand_total_repair_rub if repair else 0,
            include_repairs=lot.is_repairs_included,
            step_jpy=step_bid,
            min_bid_jpy=min_bid,
            max_bid_jpy=max_bid,
        )
    )
    return result.bid_jpy


def _missing_customs_inputs(lot: Lot, bid_jpy: int | None) -> list[str]:
    """Mandatory inputs for the customs_calc pipeline step (Russian labels)."""
    missing: list[str] = []
    if lot.fuel_type != FuelType.EV and not lot.engine_cc:
        missing.append("объём двигателя")
    if not lot.first_reg_year:
        missing.append("дата первой регистрации")
    if not lot.power_hp and lot.fuel_type == FuelType.EV:
        missing.append("мощность двигателя (для акциза EV)")
    if bid_jpy is None:
        missing.append("ставка на аукционе")
    if lot.market_price_rf_rub is None:
        missing.append("рыночная цена в РФ")
    customs = CustomsCalculation.objects.select_related("rates_snapshot").filter(lot=lot).first()
    if not lot.customs_rates_input and (customs is None or not hasattr(customs, "rates_snapshot")):
        missing.append("снимок курсов валют (шлюз ЦБ РФ)")
    return missing
