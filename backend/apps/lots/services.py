from datetime import date

from django.utils import timezone

from apps.core.enums import (
    AgeCorridor,
    AuctionHouse,
    BodyPanel,
    ChecklistItemStatus,
    CrossAuditStatus,
    DriveType,
    DutyCalculationMode,
    FrameIdConfidence,
    FuelType,
    OdometerStatus,
    PowerHpSource,
    RiskLevel,
    SystemKey,
    TrafficLightColor,
    WorkType,
)
from apps.lots.models import (
    CrossAuditReport,
    CurrencyRatesSnapshot,
    CustomsCalculation,
    DamagedPartItem,
    FarpostRepairSummary,
    Lot,
    LotDefect,
    LotRiskFlags,
    MarketComparisonInfo,
    PastAuctionRecord,
    SafetyCheckItem,
    SafetyChecklist,
    ServiceWorkItem,
    TrafficLightVerdict,
    WiseCostLadder,
    WiseCostStep,
)
from apps.users.models import User

_COROLLA_LOT_FIELDS: dict = {
    "lot_number": "3142",
    "auction_house": AuctionHouse.TAA,
    "auction_branch": "TAA Chubu",
    "auction_strictness_index": 1.0,
    "make": "Toyota",
    "model": "Corolla Touring",
    "trim": "W×B",
    "model_code": "3BA-NRE210W",
    "chassis_number": "NRE210-2005418",
    "frame_id": "NRE210-2005418",
    "frame_id_confidence": FrameIdConfidence.EXACT,
    "first_reg_year": 2020,
    "first_reg_month": 10,
    "first_reg_date_str": "10.2020 (3-5 лет, ЕАЭС)",
    "is_pass_corridor_3_5": True,
    "engine_cc": 1196,
    "power_hp": 116,
    "power_hp_source": PowerHpSource.DROM_CATALOG,
    "is_under_160_hp": True,
    "mileage_km": 58240,
    "odometer_status": OdometerStatus.CONFIRMED,
    "transmission": "6MT",
    "drive_type": DriveType.TWO_WD,
    "fuel_type": FuelType.GASOLINE,
    "color_ru": "Белый перламутр",
    "paint_code": "070",
    "overall_grade": "3.5",
    "exterior_grade": "C",
    "interior_grade": "B",
    "recycling_fee_yen": 11400,
    "recycling_fee_paid": True,
    "equipment_ru": [
        "Климат-контроль",
        "Светодиодная LED-оптика",
        "Литые диски R17",
        "Круиз-контроль",
        "Электростеклоподъемники",
        "Toyota Safety Sense (TSS)",
    ],
    "inspector_notes_ru": [
        "Царапина A2 на арке переднего крыла, вмятина U2 на пороге",
        "Заменена передняя левая дверь (XX), вторичный окрас задней двери W1 без шпаклевки",
        "Салон чистый, без прокуров, естественные следы эксплуатации (оценка B)",
        "Силовой каркас, лонжероны и геометрия в норме",
    ],
    "inspector_notes_raw": [
        "左Fドア交換(XX) / 左Rドア再塗装(W1)",
        "下廻り異常なし・室内に気になる臭いなし",
    ],
    "seller_comments_ru": [
        "Один владелец, сервисная книжка в наличии",
    ],
    "year": 2020,
    "turnkey_cost_rub": 1104899,
    "market_price_rf_rub": 1520000,
    "net_benefit_rub": 415101,
    "benefit_percentage": 37.6,
    "verdict": TrafficLightColor.GREEN,
    "verdict_headline": "🟢 РЕКОМЕНДОВАНО К ПОКУПКЕ",
    "meti_sanction_risk": False,
    "has_anomaly": False,
}

_COROLLA_DEFECTS: list[dict] = [
    {
        "panel_id": BodyPanel.FRONT_LEFT_DOOR,
        "panel_ru": "Передняя левая дверь",
        "defect_types": ["XX"],
        "severity": None,
        "raw_code": "XX",
        "description_ru": "Передняя левая дверь — замена (в цвет 070)",
    },
    {
        "panel_id": BodyPanel.FRONT_LEFT_FENDER,
        "panel_ru": "Арка переднего крыла",
        "defect_types": ["A"],
        "severity": 2,
        "raw_code": "A2",
        "description_ru": "Арка переднего крыла — царапина до 10 см",
    },
    {
        "panel_id": BodyPanel.LEFT_SILL,
        "panel_ru": "Левый порог",
        "defect_types": ["U"],
        "severity": 2,
        "raw_code": "U2",
        "description_ru": "Порог — мелкая вмятина (PDR без покраски)",
    },
    {
        "panel_id": BodyPanel.REAR_LEFT_DOOR,
        "panel_ru": "Задняя левая дверь",
        "defect_types": ["W"],
        "severity": 1,
        "raw_code": "W1",
        "description_ru": "Задняя левая дверь — вторичный заводской окрас",
    },
]

_COROLLA_RISK_FLAGS: dict = {
    "is_flooded": False,
    "airbag_deployed": False,
    "hail_damage": False,
    "underbody_rust": False,
    "underbody_corrosion": False,
    "core_support_repair": False,
    "pillar_or_frame_repair": False,
    "panel_replaced_xx": True,
    "panel_needs_replacement_x": False,
    "odometer_issue": False,
    "color_changed": False,
    "windshield_damage": False,
    "repaired_grade_r_ra": False,
}

_COROLLA_VERDICT: dict = {
    "verdict": TrafficLightColor.GREEN,
    "headline": "РЕКОМЕНДОВАНО К ПОКУПКЕ",
    "short_verdict_label": "🟢 РЕКОМЕНДОВАНО К ПОКУПКЕ",
    "badge_text": "Выгода: +415 101 ₽",
    "net_benefit_rub": 415101,
    "benefit_percentage": 37.6,
    "body_summary_ru": (
        "Кузов (оценка C): замена левой двери (XX), "
        "деталь найдена на Farpost в цвет за от 18 000 ₽."
    ),
    "interior_summary_ru": (
        "Салон (оценка B): чистый, без прокуров, мелкие естественные следы эксплуатации."
    ),
    "reasoning_bullets": [
        "Строгий аукцион TAA Chubu: оценка 3.5 C/B, родной пробег 58 240 км",
        "Несущий каркас и подушки SRS целы, повреждены только навесные панели",
        "Льготный утильсбор (5 200 ₽) и проходной коридор ЕАЭС 3-5 лет",
    ],
}

_COROLLA_MARKET: dict = {
    "market_price_rf_rub": 1520000,
    "analogs_count": 14,
    "price_min_rub": 1390000,
    "price_max_rub": 1680000,
    "search_region_ru": "ДФО / Владивосток",
    "excludes_under_order": True,
    "filtered_out_under_order_count": 6,
    "is_fallback": False,
    "fallback_reason_ru": None,
    "drom_search_url": "https://vladivostok.drom.ru/toyota/corolla_touring/year-2020/engine-1.2/manual/",
}

_COROLLA_AUDIT: dict = {
    "status": CrossAuditStatus.CLEAN,
    "source_name": "AucJP + AAA Japan / Pravto",
    "is_archive_available": True,
    "risk_level": RiskLevel.CLEAN,
    "has_critical_anomaly": False,
    "headline_ru": "Аудит истории торгов: нарушений по Frame ID не обнаружено",
    "times_auctioned": 1,
}

_COROLLA_AUDIT_HISTORY: list[dict] = [
    {
        "auction_date": date(2026, 11, 12),
        "auction_house": "TAA Chubu",
        "auction_strictness": 1.0,
        "lot_number": "3142",
        "overall_grade": "3.5",
        "mileage_km": 58240,
        "defects_summary": "Замена двери XX, окрас задней двери W1, царапина A2",
        "closing_price_jpy": 1060000,
        "sheet_archive_url": None,
    },
]

_COROLLA_SAFETY_CHECKLIST: dict = {
    "overall_status": ChecklistItemStatus.OK,
    "overall_label_ru": "В норме",
}

_COROLLA_SAFETY_ITEMS: list[dict] = [
    {
        "system_key": SystemKey.STRUCTURAL_FRAME,
        "label_ru": "Силовой каркас и лонжероны",
        "status": ChecklistItemStatus.OK,
        "detail_ru": "Нарушений геометрии, ремонта стоек и рамки радиатора на листе не отмечено",
    },
    {
        "system_key": SystemKey.AIRBAGS_SRS,
        "label_ru": "Подушки безопасности (SRS)",
        "status": ChecklistItemStatus.OK,
        "detail_ru": "Отметок о срабатывании или отсутствии подушек нет",
    },
    {
        "system_key": SystemKey.ENGINE_TRANSMISSION,
        "label_ru": "ДВС и трансмиссия",
        "status": ChecklistItemStatus.OK,
        "detail_ru": "Замечаний инспектора по работе 1.2T и 6MT в бланке нет",
    },
    {
        "system_key": SystemKey.UNDERBODY_CORROSION,
        "label_ru": "Днище и пороги",
        "status": ChecklistItemStatus.OK,
        "detail_ru": "Сквозная коррозия не отмечена",
    },
    {
        "system_key": SystemKey.FLOOD_OR_FIRE,
        "label_ru": "Следы затопления / пожара / града",
        "status": ChecklistItemStatus.OK,
        "detail_ru": "Стоп-факторов в бланке не зафиксировано",
    },
]

_COROLLA_CUSTOMS: dict = {
    "age_corridor": AgeCorridor.THREE_TO_FIVE_YEARS,
    "duty_calculation_mode": DutyCalculationMode.EUR_PER_CC,
    "engine_cc": 1196,
    "duty_rate_eur_per_cc": 1.7,
    "effective_duty_pct": None,
    "customs_duty_eur": 2033.2,
    "customs_duty_rub": 193154,
    "is_under_160_hp": True,
    "is_commercial_util": False,
    "utilization_fee_rub": 5200,
    "customs_clearance_fee_rub": 3120,
    "freight_vladivostok_rub": 97750,
    "broker_svh_sbkts_rub": 99000,
    "meti_sanction_risk": False,
}

_COROLLA_RATES_SNAPSHOT: dict = {
    "jpy_rub_bank": 0.585,
    "jpy_rate_source": "ДВ-банк (ориентир)",
    "eur_rub_cbrf": 95.0,
    "usd_rub_cbrf": 85.0,
    "cbrf_date": "12.11.2026",
}

_COROLLA_FARPOST_SUMMARY: dict = {
    "total_parts_from_rub": 18000,
    "total_works_rub": 13000,
    "grand_total_repair_rub": 31000,
    "has_color_matched_parts": True,
    "included_in_turnkey_hint_ru": "Сумма уже включена в расчёт под ключ",
}

_COROLLA_FARPOST_PARTS: list[dict] = [
    {
        "panel_id": BodyPanel.FRONT_LEFT_DOOR,
        "defect_code": "XX",
        "part_name_ru": "Передняя левая дверь",
        "subtitle_ru": "контрактная деталь в заводской цвет 070",
        "price_from_rub": 18000,
        "in_stock_vladivostok": True,
        "is_statistical_fallback": False,
    },
]

_COROLLA_FARPOST_WORKS: list[dict] = [
    {
        "work_type": WorkType.MOUNT_DISMOUNT,
        "label_ru": "Снятие и монтаж двери",
        "amount_rub": 4000,
        "zero_cost_reason_ru": None,
    },
    {
        "work_type": WorkType.PAINT,
        "label_ru": "Покраска двери (в цвет 070)",
        "amount_rub": 0,
        "zero_cost_reason_ru": "не требуется",
    },
    {
        "work_type": WorkType.PDR_AND_POLISH,
        "label_ru": "PDR удаление вмятины + полировка",
        "amount_rub": 9000,
        "zero_cost_reason_ru": None,
    },
]

_COROLLA_WISE_COST_LADDER: dict = {
    "car_bid_jpy": 1060000,
    "car_bid_rub": 620100,
    "turnkey_cost_rub": 1104899,
    "market_price_rf_rub": 1520000,
    "net_benefit_rub": 415101,
    "benefit_percentage": 37.6,
}

_COROLLA_WISE_COST_STEPS: list[dict] = [
    {
        "step_number": 1,
        "name_ru": "Ставка на аукционе",
        "amount_rub": 620100,
        "original_currency": "JPY",
        "original_amount": 1060000.0,
        "is_optional": False,
    },
    {
        "step_number": 2,
        "name_ru": "Расходы в Японии (FOB и сбор)",
        "amount_rub": 55575,
        "original_currency": "JPY",
        "original_amount": 95000.0,
        "is_optional": False,
    },
    {
        "step_number": 3,
        "name_ru": "Фрахт Тояма-ВЛК",
        "amount_rub": 97750,
        "original_currency": "USD",
        "original_amount": 1150.0,
        "is_optional": False,
    },
    {
        "step_number": 4,
        "name_ru": "Таможенная пошлина ЕАЭС и сбор",
        "amount_rub": 196274,
        "original_currency": "EUR",
        "original_amount": 2033.2,
        "is_optional": False,
    },
    {
        "step_number": 5,
        "name_ru": "Утилизационный сбор РФ",
        "amount_rub": 5200,
        "original_currency": "RUB",
        "original_amount": 5200.0,
        "is_optional": False,
    },
    {
        "step_number": 6,
        "name_ru": "СВХ, брокер, СБКТС, ЭПТС",
        "amount_rub": 99000,
        "original_currency": "RUB",
        "original_amount": 99000.0,
        "is_optional": False,
    },
    {
        "step_number": 7,
        "name_ru": "Запчасти Farpost и ремонт",
        "amount_rub": 31000,
        "original_currency": "RUB",
        "original_amount": 31000.0,
        "is_optional": True,
    },
]

_SIMPLE_STARTER_LOTS: list[dict] = [
    {
        "make": "Honda",
        "model": "Vezel",
        "trim": "Hybrid",
        "year": 2019,
        "frame_id": "RU3-1209412",
        "chassis_number": "RU3-1209412",
        "auction_house": AuctionHouse.USS,
        "overall_grade": "4.0",
        "fuel_type": FuelType.HYBRID,
        "meti_sanction_risk": True,
        "turnkey_cost_rub": 1480000,
        "market_price_rf_rub": 1600000,
        "net_benefit_rub": 120000,
        "benefit_percentage": 8.1,
        "verdict": TrafficLightColor.YELLOW,
        "verdict_headline": "🟡 ВНИМАНИЕ: СКОЛЫ A2/U2",
        "has_anomaly": False,
    },
    {
        "make": "Nissan",
        "model": "Note",
        "trim": "e-Power",
        "year": 2021,
        "frame_id": "HE12-389104",
        "chassis_number": "HE12-389104",
        "overall_grade": "4.5",
        "fuel_type": FuelType.HYBRID,
        "meti_sanction_risk": True,
        "turnkey_cost_rub": 980000,
        "market_price_rf_rub": 1190000,
        "net_benefit_rub": 210000,
        "benefit_percentage": 21.4,
        "verdict": TrafficLightColor.GREEN,
        "verdict_headline": "🟢 РЕКОМЕНДОВАНО К ПОКУПКЕ",
        "has_anomaly": False,
    },
]


def _seed_corolla(user: User, now) -> Lot:
    lot = Lot.objects.create(user=user, completed_at=now, **_COROLLA_LOT_FIELDS)

    for defect_data in _COROLLA_DEFECTS:
        LotDefect.objects.create(lot=lot, **defect_data)

    LotRiskFlags.objects.create(lot=lot, **_COROLLA_RISK_FLAGS)
    TrafficLightVerdict.objects.create(lot=lot, **_COROLLA_VERDICT)
    MarketComparisonInfo.objects.create(lot=lot, **_COROLLA_MARKET)

    audit = CrossAuditReport.objects.create(lot=lot, verified_at=now, **_COROLLA_AUDIT)
    for history_data in _COROLLA_AUDIT_HISTORY:
        PastAuctionRecord.objects.create(audit=audit, **history_data)

    checklist = SafetyChecklist.objects.create(lot=lot, **_COROLLA_SAFETY_CHECKLIST)
    for item_data in _COROLLA_SAFETY_ITEMS:
        SafetyCheckItem.objects.create(checklist=checklist, **item_data)

    customs = CustomsCalculation.objects.create(lot=lot, **_COROLLA_CUSTOMS)
    CurrencyRatesSnapshot.objects.create(customs=customs, **_COROLLA_RATES_SNAPSHOT)

    repair = FarpostRepairSummary.objects.create(lot=lot, **_COROLLA_FARPOST_SUMMARY)
    for part_data in _COROLLA_FARPOST_PARTS:
        DamagedPartItem.objects.create(repair=repair, **part_data)
    for work_data in _COROLLA_FARPOST_WORKS:
        ServiceWorkItem.objects.create(repair=repair, **work_data)

    ladder = WiseCostLadder.objects.create(lot=lot, **_COROLLA_WISE_COST_LADDER)
    for step_data in _COROLLA_WISE_COST_STEPS:
        WiseCostStep.objects.create(ladder=ladder, **step_data)

    return lot


def seed_starter_lots(user: User) -> None:
    """Create benchmark starter lots for a newly registered user."""
    now = timezone.now()
    _seed_corolla(user, now)
    for lot_data in _SIMPLE_STARTER_LOTS:
        Lot.objects.create(user=user, completed_at=now, **lot_data)
