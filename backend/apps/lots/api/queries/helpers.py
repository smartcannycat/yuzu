"""Shared query serialization builders for lots and related domain tables."""

import math

from apps.core.enums import (
    AuctionHouse,
    FrameIdConfidence,
    OdometerStatus,
)
from apps.lots.api import schemas
from apps.lots.calculator.economics import is_simulation_modified
from apps.lots.models import (
    CrossAuditReport,
    CustomsCalculation,
    FarpostRepairSummary,
    Lot,
    SafetyChecklist,
    WiseCostLadder,
)


def _build_thumbnail_url(lot: Lot) -> str | None:
    return lot.sheet_thumbnail.url if lot.sheet_thumbnail else None


def _build_lot_summary(lot: Lot) -> schemas.LotSummary:
    return schemas.LotSummary(
        lot_id=lot.id,
        make=lot.make,
        model=lot.model,
        year=lot.year,
        engine_cc=lot.engine_cc,
        frame_id=lot.frame_id,
        auction_house=lot.auction_house,
        lot_number=lot.lot_number,
        overall_grade=lot.overall_grade,
        mileage_km=lot.mileage_km,
        turnkey_cost_rub=lot.turnkey_cost_rub,
        market_price_rf_rub=lot.market_price_rf_rub,
        verdict=lot.verdict,
        verdict_headline=lot.verdict_headline,
        net_benefit_rub=lot.net_benefit_rub,
        meti_sanction_risk=lot.meti_sanction_risk,
        has_anomaly=lot.has_anomaly,
        anomaly_text=lot.anomaly_text,
        thumbnail_url=_build_thumbnail_url(lot),
        auction_date=lot.auction_date,
        is_archived=lot.is_archived,
        archived_at=lot.archived_at,
        archived_reason=lot.archived_reason,
        expires_at=lot.expires_at,
        created_at=lot.created_at,
    )


def _sanitize_strictness_index(value: float | None) -> float:
    if value is None or not math.isfinite(value):
        return 0.65
    if 1.0 < value <= 5.0:
        return round(value / 5.0, 2)
    return max(0.0, min(1.0, float(value)))


def _build_normalized_sheet(lot: Lot) -> schemas.NormalizedSheet:
    return schemas.NormalizedSheet(
        lot_number=lot.lot_number,
        auction_house=lot.auction_house or AuctionHouse.OTHER.value,
        auction_branch=lot.auction_branch,
        auction_date=lot.auction_date,
        auction_strictness_index=_sanitize_strictness_index(lot.auction_strictness_index),
        make=lot.make,
        model=lot.model,
        trim=lot.trim,
        model_code=lot.model_code or "",
        chassis_number=lot.chassis_number or "",
        frame_id=lot.frame_id,
        frame_id_confidence=lot.frame_id_confidence or FrameIdConfidence.RAW,
        first_reg_year=lot.first_reg_year,
        first_reg_month=lot.first_reg_month,
        first_reg_date_str=lot.first_reg_date_str,
        is_pass_corridor_3_5=lot.is_pass_corridor_3_5,
        engine_cc=lot.engine_cc,
        power_hp=lot.power_hp,
        power_hp_source=lot.power_hp_source,
        is_under_160_hp=lot.is_under_160_hp,
        mileage_km=lot.mileage_km,
        odometer_status=lot.odometer_status or OdometerStatus.UNKNOWN,
        transmission=lot.transmission or "не указана",
        drive_type=lot.drive_type,
        fuel_type=lot.fuel_type,
        color_ru=lot.color_ru,
        paint_code=lot.paint_code,
        overall_grade=lot.overall_grade,
        exterior_grade=lot.exterior_grade,
        interior_grade=lot.interior_grade,
        shaken_until=lot.shaken_until,
        recycling_fee_yen=lot.recycling_fee_yen,
        recycling_fee_paid=lot.recycling_fee_paid,
        equipment_ru=lot.equipment_ru,
        defects=[schemas.NormalizedDefect.model_validate(d) for d in lot.defects.all()],
        risk_flags=schemas.RiskFlags.model_validate(lot.risk_flags),
        inspector_notes_ru=lot.inspector_notes_ru,
        inspector_notes_raw=lot.inspector_notes_raw,
        seller_comments_ru=lot.seller_comments_ru,
        extra_ru=lot.extra_ru,
        ocr_warnings=lot.ocr_warnings,
        low_confidence_fields=lot.low_confidence_fields,
    )


def _build_audit_out(audit: CrossAuditReport) -> schemas.CrossAuditReport:
    return schemas.CrossAuditReport(
        status=audit.status,
        source_name=audit.source_name,
        is_archive_available=audit.is_archive_available,
        risk_level=audit.risk_level,
        has_critical_anomaly=audit.has_critical_anomaly,
        headline_ru=audit.headline_ru,
        times_auctioned=audit.times_auctioned,
        verified_at=audit.verified_at,
        anomalies=[schemas.AnomalyAlert.model_validate(a) for a in audit.anomalies.all()],
        history=[schemas.PastAuctionRecord.model_validate(h) for h in audit.history.all()],
    )


def _build_safety_out(checklist: SafetyChecklist) -> schemas.SafetyChecklist:
    return schemas.SafetyChecklist(
        overall_status=checklist.overall_status,
        overall_label_ru=checklist.overall_label_ru,
        items=[schemas.SafetyCheckItem.model_validate(i) for i in checklist.items.all()],
    )


def _build_customs_out(customs: CustomsCalculation) -> schemas.CustomsCalculation:
    return schemas.CustomsCalculation(
        age_corridor=customs.age_corridor,
        duty_calculation_mode=customs.duty_calculation_mode,
        engine_cc=customs.engine_cc,
        duty_rate_eur_per_cc=customs.duty_rate_eur_per_cc,
        effective_duty_pct=customs.effective_duty_pct,
        customs_duty_eur=customs.customs_duty_eur,
        customs_duty_rub=customs.customs_duty_rub,
        excise_rub=customs.excise_rub,
        import_vat_rub=customs.import_vat_rub,
        is_under_160_hp=customs.is_under_160_hp,
        is_commercial_util=customs.is_commercial_util,
        utilization_fee_rub=customs.utilization_fee_rub,
        customs_clearance_fee_rub=customs.customs_clearance_fee_rub,
        freight_vladivostok_rub=customs.freight_vladivostok_rub,
        broker_svh_sbkts_rub=customs.broker_svh_sbkts_rub,
        meti_sanction_risk=customs.meti_sanction_risk,
        rates_snapshot=schemas.CurrencyRates.model_validate(customs.rates_snapshot),
    )


def _build_farpost_out(repair: FarpostRepairSummary) -> schemas.FarpostRepairSummary:
    return schemas.FarpostRepairSummary(
        parts=[schemas.DamagedPartItem.model_validate(p) for p in repair.parts.all()],
        service_works=[
            schemas.ServiceWorkItem.model_validate(w) for w in repair.service_works.all()
        ],
        total_parts_from_rub=repair.total_parts_from_rub,
        total_works_rub=repair.total_works_rub,
        grand_total_repair_rub=repair.grand_total_repair_rub,
        has_color_matched_parts=repair.has_color_matched_parts,
        included_in_turnkey_hint_ru=repair.included_in_turnkey_hint_ru,
    )


def _build_wise_cost_out(ladder: WiseCostLadder) -> schemas.WiseCostLadder:
    return schemas.WiseCostLadder(
        car_bid_jpy=ladder.car_bid_jpy,
        car_bid_rub=ladder.car_bid_rub,
        turnkey_cost_rub=ladder.turnkey_cost_rub,
        market_price_rf_rub=ladder.market_price_rf_rub,
        net_benefit_rub=ladder.net_benefit_rub,
        benefit_percentage=ladder.benefit_percentage,
        steps=[schemas.WiseCostStep.model_validate(s) for s in ladder.steps.all()],
    )


def _build_economics(lot: Lot) -> schemas.EconomicsDetail:
    return schemas.EconomicsDetail(
        bid_slider_min_jpy=lot.bid_slider_min_jpy,
        bid_slider_max_jpy=lot.bid_slider_max_jpy,
        bid_slider_step_jpy=lot.bid_slider_step_jpy,
        is_repairs_included=lot.is_repairs_included,
        is_simulation_modified=is_simulation_modified(lot, lot.customs_calc, lot.wise_cost_ladder),
        customs=_build_customs_out(lot.customs_calc),
        farpost_repair=_build_farpost_out(lot.farpost_repair),
        wise_cost_ladder=_build_wise_cost_out(lot.wise_cost_ladder),
    )


def _build_media_links(lot: Lot) -> schemas.LotMediaLinks:
    return schemas.LotMediaLinks(
        sheet_thumbnail_url=lot.sheet_thumbnail.url if lot.sheet_thumbnail else "",
        sheet_scan_url=lot.sheet_scan.url if lot.sheet_scan else "",
        drom_search_url=lot.market_info.drom_search_url,
    )
