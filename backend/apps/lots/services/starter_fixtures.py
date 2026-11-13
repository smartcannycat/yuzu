from datetime import date

from django.db import transaction
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

_VEZEL_LOT_FIELDS: dict = {
    "lot_number": "5094",
    "auction_house": AuctionHouse.USS,
    "auction_branch": "USS Tokyo",
    "auction_strictness_index": 0.85,
    "make": "Honda",
    "model": "Vezel",
    "trim": "Hybrid",
    "model_code": "RU3",
    "chassis_number": "RU3-1209412",
    "frame_id": "RU3-1209412",
    "frame_id_confidence": FrameIdConfidence.EXACT,
    "first_reg_year": 2022,
    "first_reg_month": 3,
    "first_reg_date_str": "03.2022 (3-5 лет, ЕАЭС)",
    "is_pass_corridor_3_5": True,
    "engine_cc": 1496,
    "power_hp": 131,
    "power_hp_source": PowerHpSource.DROM_CATALOG,
    "is_under_160_hp": True,
    "mileage_km": 45000,
    "odometer_status": OdometerStatus.CONFIRMED,
    "transmission": "CVT",
    "drive_type": DriveType.FOUR_WD,
    "fuel_type": FuelType.HYBRID,
    "color_ru": "Серебристый металлик",
    "paint_code": "NH707M",
    "overall_grade": "4.0",
    "exterior_grade": "A",
    "interior_grade": "A",
    "recycling_fee_yen": 13200,
    "recycling_fee_paid": True,
    "equipment_ru": [
        "Климат-контроль",
        "Светодиодная оптика",
        "Литые диски R17",
        "Камера заднего вида",
        "Honda Sensing",
    ],
    "inspector_notes_ru": [
        "Сколы A2 на переднем бампере и вмятина U2 на задней двери",
        "Салон чистый, без замечаний (оценка A)",
    ],
    "inspector_notes_raw": [
        "前バンパー A2 / 後ドア U2",
    ],
    "seller_comments_ru": [
        "Один владелец, не курили в салоне",
    ],
    "year": 2022,
    "turnkey_cost_rub": 1480000,
    "market_price_rf_rub": 1600000,
    "net_benefit_rub": 120000,
    "benefit_percentage": 8.1,
    "verdict": TrafficLightColor.YELLOW,
    "verdict_headline": "🟡 ВНИМАНИЕ: СКОЛЫ A2/U2",
    "meti_sanction_risk": True,
    "has_anomaly": False,
}

_VEZEL_DEFECTS: list[dict] = [
    {
        "panel_id": BodyPanel.FRONT_BUMPER,
        "panel_ru": "Передний бампер",
        "defect_types": ["A"],
        "severity": 2,
        "raw_code": "A2",
        "description_ru": "Передний бампер — сколы до 10 см",
    },
    {
        "panel_id": BodyPanel.REAR_LEFT_DOOR,
        "panel_ru": "Задняя левая дверь",
        "defect_types": ["U"],
        "severity": 2,
        "raw_code": "U2",
        "description_ru": "Задняя левая дверь — вмятина (PDR без покраски)",
    },
]

_VEZEL_RISK_FLAGS: dict = dict.fromkeys(
    (
        "is_flooded",
        "airbag_deployed",
        "hail_damage",
        "underbody_rust",
        "underbody_corrosion",
        "core_support_repair",
        "pillar_or_frame_repair",
        "panel_replaced_xx",
        "panel_needs_replacement_x",
        "odometer_issue",
        "color_changed",
        "windshield_damage",
        "repaired_grade_r_ra",
    ),
    False,
)

_VEZEL_VERDICT: dict = {
    "verdict": TrafficLightColor.YELLOW,
    "headline": "ВНИМАНИЕ: СКОЛЫ A2/U2",
    "short_verdict_label": "🟡 ВНИМАНИЕ: СКОЛЫ A2/U2",
    "badge_text": "Выгода: +120 000 ₽",
    "net_benefit_rub": 120000,
    "benefit_percentage": 8.1,
    "body_summary_ru": (
        "Кузов (оценка A): сколы A2 на бампере и вмятина U2 на двери, "
        "ремонт PDR без замены деталей."
    ),
    "interior_summary_ru": "Салон (оценка A): чистый, без замечаний.",
    "reasoning_bullets": [
        "Гибрид Honda Vezel: санкционный риск METI, но мощность 131 л.с. < 160 л.с.",
        "Оценка 4.0 A/A, родной пробег 45 000 км",
        "Ремонт ограничен сколами и вмятинами без замены панелей",
    ],
}

_VEZEL_MARKET: dict = {
    "market_price_rf_rub": 1600000,
    "analogs_count": 8,
    "price_min_rub": 1450000,
    "price_max_rub": 1850000,
    "search_region_ru": "ДФО / Владивосток",
    "excludes_under_order": True,
    "filtered_out_under_order_count": 4,
    "is_fallback": False,
    "fallback_reason_ru": None,
    "drom_search_url": "https://vladivostok.drom.ru/honda/vezel/year-2022/engine-1.5/4wd/",
}

_VEZEL_AUDIT: dict = {
    "status": CrossAuditStatus.CLEAN,
    "source_name": "AucJP + AAA Japan / Pravto",
    "is_archive_available": True,
    "risk_level": RiskLevel.CLEAN,
    "has_critical_anomaly": False,
    "headline_ru": "Аудит истории торгов: нарушений по Frame ID не обнаружено",
    "times_auctioned": 1,
}

_VEZEL_AUDIT_HISTORY: list[dict] = [
    {
        "auction_date": date(2026, 11, 11),
        "auction_house": "USS Tokyo",
        "auction_strictness": 0.85,
        "lot_number": "5094",
        "overall_grade": "4.0",
        "mileage_km": 45000,
        "defects_summary": "Сколы A2 на бампере, вмятина U2 на двери",
        "closing_price_jpy": 1700000,
        "sheet_archive_url": None,
    },
]

_VEZEL_SAFETY_CHECKLIST: dict = {
    "overall_status": ChecklistItemStatus.OK,
    "overall_label_ru": "В норме",
}

_VEZEL_SAFETY_ITEMS: list[dict] = [
    {
        "system_key": SystemKey.STRUCTURAL_FRAME,
        "label_ru": "Силовой каркас и лонжероны",
        "status": ChecklistItemStatus.OK,
        "detail_ru": "Нарушений геометрии и ремонта несущих элементов не отмечено",
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
        "detail_ru": "Гибридная установка i-MMD без замечаний инспектора",
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

_VEZEL_CUSTOMS: dict = {
    "age_corridor": AgeCorridor.THREE_TO_FIVE_YEARS,
    "duty_calculation_mode": DutyCalculationMode.EUR_PER_CC,
    "engine_cc": 1496,
    "duty_rate_eur_per_cc": 1.7,
    "effective_duty_pct": None,
    "customs_duty_eur": 2517.68,
    "customs_duty_rub": 239180,
    "is_under_160_hp": True,
    "is_commercial_util": False,
    "utilization_fee_rub": 5200,
    "customs_clearance_fee_rub": 3120,
    "freight_vladivostok_rub": 95000,
    "broker_svh_sbkts_rub": 65000,
    "meti_sanction_risk": True,
}

_VEZEL_RATES_SNAPSHOT: dict = {
    "jpy_rub_bank": 0.585,
    "jpy_rate_source": "ДВ-банк (ориентир)",
    "eur_rub_cbrf": 95.0,
    "usd_rub_cbrf": 85.0,
    "cbrf_date": "12.11.2026",
}

_VEZEL_FARPOST_SUMMARY: dict = {
    "total_parts_from_rub": 0,
    "total_works_rub": 18000,
    "grand_total_repair_rub": 18000,
    "has_color_matched_parts": False,
    "included_in_turnkey_hint_ru": "Сумма уже включена в расчёт под ключ",
}

_VEZEL_FARPOST_WORKS: list[dict] = [
    {
        "work_type": WorkType.PDR_AND_POLISH,
        "label_ru": "PDR удаление вмятины + полировка сколов",
        "amount_rub": 18000,
        "zero_cost_reason_ru": None,
    },
]

_VEZEL_WISE_COST_LADDER: dict = {
    "car_bid_jpy": 1700000,
    "car_bid_rub": 994500,
    "turnkey_cost_rub": 1480000,
    "market_price_rf_rub": 1600000,
    "net_benefit_rub": 120000,
    "benefit_percentage": 8.1,
}

_VEZEL_WISE_COST_STEPS: list[dict] = [
    {
        "step_number": 1,
        "name_ru": "Ставка на аукционе",
        "amount_rub": 994500,
        "original_currency": "JPY",
        "original_amount": 1700000.0,
        "is_optional": False,
    },
    {
        "step_number": 2,
        "name_ru": "Расходы в Японии (FOB и сбор)",
        "amount_rub": 60000,
        "original_currency": "JPY",
        "original_amount": 102500.0,
        "is_optional": False,
    },
    {
        "step_number": 3,
        "name_ru": "Фрахт Тояма-ВЛК",
        "amount_rub": 95000,
        "original_currency": "USD",
        "original_amount": 1117.0,
        "is_optional": False,
    },
    {
        "step_number": 4,
        "name_ru": "Таможенная пошлина ЕАЭС и сбор",
        "amount_rub": 242300,
        "original_currency": "EUR",
        "original_amount": 2517.68,
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
        "amount_rub": 65000,
        "original_currency": "RUB",
        "original_amount": 65000.0,
        "is_optional": False,
    },
    {
        "step_number": 7,
        "name_ru": "Запчасти Farpost и ремонт",
        "amount_rub": 18000,
        "original_currency": "RUB",
        "original_amount": 18000.0,
        "is_optional": True,
    },
]

_NOTE_LOT_FIELDS: dict = {
    "lot_number": "7281",
    "auction_house": AuctionHouse.CAA,
    "auction_branch": "CAA Kanto",
    "auction_strictness_index": 0.80,
    "make": "Nissan",
    "model": "Note",
    "trim": "e-Power",
    "model_code": "HE12",
    "chassis_number": "HE12-389104",
    "frame_id": "HE12-389104",
    "frame_id_confidence": FrameIdConfidence.EXACT,
    "first_reg_year": 2024,
    "first_reg_month": 6,
    "first_reg_date_str": "06.2024 (до 3 лет, ЕАЭС)",
    "is_pass_corridor_3_5": False,
    "engine_cc": 1198,
    "power_hp": 109,
    "power_hp_source": PowerHpSource.DROM_CATALOG,
    "is_under_160_hp": True,
    "mileage_km": 65000,
    "odometer_status": OdometerStatus.CONFIRMED,
    "transmission": "CVT",
    "drive_type": DriveType.TWO_WD,
    "fuel_type": FuelType.HYBRID,
    "color_ru": "Белый перламутр",
    "paint_code": "WW3",
    "overall_grade": "4.5",
    "exterior_grade": "A",
    "interior_grade": "A",
    "recycling_fee_yen": 12800,
    "recycling_fee_paid": True,
    "equipment_ru": [
        "Климат-контроль",
        "Камера заднего вида",
        "Подогрев сидений",
        "Nissan Safety Shield",
    ],
    "inspector_notes_ru": [
        "Состояние отличное, мелкие царапины W1 на переднем крыле",
        "Салон новый, без следов эксплуатации (оценка A)",
    ],
    "inspector_notes_raw": [
        "前フェンダー W1",
    ],
    "seller_comments_ru": [
        "Первый владелец, сервисная история доступна",
    ],
    "year": 2024,
    "turnkey_cost_rub": 980000,
    "market_price_rf_rub": 1190000,
    "net_benefit_rub": 210000,
    "benefit_percentage": 21.4,
    "verdict": TrafficLightColor.GREEN,
    "verdict_headline": "🟢 РЕКОМЕНДОВАНО К ПОКУПКЕ",
    "meti_sanction_risk": True,
    "has_anomaly": False,
}

_NOTE_DEFECTS: list[dict] = [
    {
        "panel_id": BodyPanel.FRONT_LEFT_FENDER,
        "panel_ru": "Переднее левое крыло",
        "defect_types": ["W"],
        "severity": 1,
        "raw_code": "W1",
        "description_ru": "Переднее левое крыло — мелкий вторичный окрас",
    },
]

_NOTE_RISK_FLAGS: dict = dict.fromkeys(
    (
        "is_flooded",
        "airbag_deployed",
        "hail_damage",
        "underbody_rust",
        "underbody_corrosion",
        "core_support_repair",
        "pillar_or_frame_repair",
        "panel_replaced_xx",
        "panel_needs_replacement_x",
        "odometer_issue",
        "color_changed",
        "windshield_damage",
        "repaired_grade_r_ra",
    ),
    False,
)

_NOTE_VERDICT: dict = {
    "verdict": TrafficLightColor.GREEN,
    "headline": "РЕКОМЕНДОВАНО К ПОКУПКЕ",
    "short_verdict_label": "🟢 РЕКОМЕНДОВАНО К ПОКУПКЕ",
    "badge_text": "Выгода: +210 000 ₽",
    "net_benefit_rub": 210000,
    "benefit_percentage": 21.4,
    "body_summary_ru": ("Кузов (оценка A): только мелкий вторичный окрас W1 на переднем крыле."),
    "interior_summary_ru": "Салон (оценка A): новый, без следов эксплуатации.",
    "reasoning_bullets": [
        "Nissan Note e-Power: гибрид, санкционный риск METI, но 109 л.с. < 160 л.с.",
        "Оценка 4.5 A/A, родной пробег 65 000 км",
        "Льготный утильсбор и коридор до 3 лет, ремонт не требуется",
    ],
}

_NOTE_MARKET: dict = {
    "market_price_rf_rub": 1190000,
    "analogs_count": 6,
    "price_min_rub": 1090000,
    "price_max_rub": 1390000,
    "search_region_ru": "ДФО / Владивосток",
    "excludes_under_order": True,
    "filtered_out_under_order_count": 3,
    "is_fallback": False,
    "fallback_reason_ru": None,
    "drom_search_url": "https://vladivostok.drom.ru/nissan/note/year-2024/engine-1.2/",
}

_NOTE_AUDIT: dict = {
    "status": CrossAuditStatus.CLEAN,
    "source_name": "AucJP + AAA Japan / Pravto",
    "is_archive_available": True,
    "risk_level": RiskLevel.CLEAN,
    "has_critical_anomaly": False,
    "headline_ru": "Аудит истории торгов: нарушений по Frame ID не обнаружено",
    "times_auctioned": 1,
}

_NOTE_AUDIT_HISTORY: list[dict] = [
    {
        "auction_date": date(2026, 11, 10),
        "auction_house": "CAA Kanto",
        "auction_strictness": 0.80,
        "lot_number": "7281",
        "overall_grade": "4.5",
        "mileage_km": 65000,
        "defects_summary": "Мелкий вторичный окрас W1 на переднем крыле",
        "closing_price_jpy": 1200000,
        "sheet_archive_url": None,
    },
]

_NOTE_SAFETY_CHECKLIST: dict = {
    "overall_status": ChecklistItemStatus.OK,
    "overall_label_ru": "В норме",
}

_NOTE_SAFETY_ITEMS: list[dict] = [
    {
        "system_key": SystemKey.STRUCTURAL_FRAME,
        "label_ru": "Силовой каркас и лонжероны",
        "status": ChecklistItemStatus.OK,
        "detail_ru": "Нарушений геометрии и ремонта несущих элементов не отмечено",
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
        "detail_ru": "Гибридная установка e-Power без замечаний инспектора",
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

_NOTE_CUSTOMS: dict = {
    "age_corridor": AgeCorridor.UNDER_3_YEARS,
    "duty_calculation_mode": DutyCalculationMode.PCT_OF_VALUE,
    "engine_cc": 1198,
    "duty_rate_eur_per_cc": None,
    "effective_duty_pct": 48.0,
    "customs_duty_eur": 576.0,
    "customs_duty_rub": 54720,
    "is_under_160_hp": True,
    "is_commercial_util": False,
    "utilization_fee_rub": 5200,
    "customs_clearance_fee_rub": 3100,
    "freight_vladivostok_rub": 90000,
    "broker_svh_sbkts_rub": 27980,
    "meti_sanction_risk": True,
}

_NOTE_RATES_SNAPSHOT: dict = {
    "jpy_rub_bank": 0.585,
    "jpy_rate_source": "ДВ-банк (ориентир)",
    "eur_rub_cbrf": 95.0,
    "usd_rub_cbrf": 85.0,
    "cbrf_date": "12.11.2026",
}

_NOTE_FARPOST_SUMMARY: dict = {
    "total_parts_from_rub": 0,
    "total_works_rub": 0,
    "grand_total_repair_rub": 0,
    "has_color_matched_parts": False,
    "included_in_turnkey_hint_ru": "Сумма уже включена в расчёт под ключ",
}

_NOTE_WISE_COST_LADDER: dict = {
    "car_bid_jpy": 1200000,
    "car_bid_rub": 702000,
    "turnkey_cost_rub": 980000,
    "market_price_rf_rub": 1190000,
    "net_benefit_rub": 210000,
    "benefit_percentage": 21.4,
}

_NOTE_WISE_COST_STEPS: list[dict] = [
    {
        "step_number": 1,
        "name_ru": "Ставка на аукционе",
        "amount_rub": 702000,
        "original_currency": "JPY",
        "original_amount": 1200000.0,
        "is_optional": False,
    },
    {
        "step_number": 2,
        "name_ru": "Расходы в Японии (FOB и сбор)",
        "amount_rub": 97000,
        "original_currency": "JPY",
        "original_amount": 165800.0,
        "is_optional": False,
    },
    {
        "step_number": 3,
        "name_ru": "Фрахт Тояма-ВЛК",
        "amount_rub": 90000,
        "original_currency": "USD",
        "original_amount": 1058.0,
        "is_optional": False,
    },
    {
        "step_number": 4,
        "name_ru": "Таможенная пошлина ЕАЭС и сбор",
        "amount_rub": 57820,
        "original_currency": "EUR",
        "original_amount": 576.0,
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
        "amount_rub": 27980,
        "original_currency": "RUB",
        "original_amount": 27980.0,
        "is_optional": False,
    },
    {
        "step_number": 7,
        "name_ru": "Запчасти Farpost и ремонт",
        "amount_rub": 0,
        "original_currency": "RUB",
        "original_amount": 0.0,
        "is_optional": True,
    },
]


_STARTER_FIXTURES: dict[tuple[str, str], dict] = {}


def _register_starter_fixtures() -> None:
    for lot_fields, kwargs in (
        (
            _COROLLA_LOT_FIELDS,
            {
                "defects": _COROLLA_DEFECTS,
                "risk_flags": _COROLLA_RISK_FLAGS,
                "verdict": _COROLLA_VERDICT,
                "market": _COROLLA_MARKET,
                "audit": _COROLLA_AUDIT,
                "audit_history": _COROLLA_AUDIT_HISTORY,
                "safety": _COROLLA_SAFETY_CHECKLIST,
                "safety_items": _COROLLA_SAFETY_ITEMS,
                "customs": _COROLLA_CUSTOMS,
                "rates": _COROLLA_RATES_SNAPSHOT,
                "farpost": _COROLLA_FARPOST_SUMMARY,
                "farpost_parts": _COROLLA_FARPOST_PARTS,
                "farpost_works": _COROLLA_FARPOST_WORKS,
                "wise_cost": _COROLLA_WISE_COST_LADDER,
                "wise_cost_steps": _COROLLA_WISE_COST_STEPS,
            },
        ),
        (
            _VEZEL_LOT_FIELDS,
            {
                "defects": _VEZEL_DEFECTS,
                "risk_flags": _VEZEL_RISK_FLAGS,
                "verdict": _VEZEL_VERDICT,
                "market": _VEZEL_MARKET,
                "audit": _VEZEL_AUDIT,
                "audit_history": _VEZEL_AUDIT_HISTORY,
                "safety": _VEZEL_SAFETY_CHECKLIST,
                "safety_items": _VEZEL_SAFETY_ITEMS,
                "customs": _VEZEL_CUSTOMS,
                "rates": _VEZEL_RATES_SNAPSHOT,
                "farpost": _VEZEL_FARPOST_SUMMARY,
                "farpost_works": _VEZEL_FARPOST_WORKS,
                "wise_cost": _VEZEL_WISE_COST_LADDER,
                "wise_cost_steps": _VEZEL_WISE_COST_STEPS,
            },
        ),
        (
            _NOTE_LOT_FIELDS,
            {
                "defects": _NOTE_DEFECTS,
                "risk_flags": _NOTE_RISK_FLAGS,
                "verdict": _NOTE_VERDICT,
                "market": _NOTE_MARKET,
                "audit": _NOTE_AUDIT,
                "audit_history": _NOTE_AUDIT_HISTORY,
                "safety": _NOTE_SAFETY_CHECKLIST,
                "safety_items": _NOTE_SAFETY_ITEMS,
                "customs": _NOTE_CUSTOMS,
                "rates": _NOTE_RATES_SNAPSHOT,
                "farpost": _NOTE_FARPOST_SUMMARY,
                "wise_cost": _NOTE_WISE_COST_LADDER,
                "wise_cost_steps": _NOTE_WISE_COST_STEPS,
            },
        ),
    ):
        key = (lot_fields["make"], lot_fields["model"])
        _STARTER_FIXTURES[key] = {"lot_fields": lot_fields, **kwargs}


_register_starter_fixtures()


def _create_lot_relations(
    lot: Lot, now, *, fixture: dict, customs_model=CustomsCalculation
) -> None:
    for defect_data in fixture.get("defects") or []:
        LotDefect.objects.create(lot=lot, **defect_data)

    LotRiskFlags.objects.create(lot=lot, **fixture["risk_flags"])
    TrafficLightVerdict.objects.create(lot=lot, **fixture["verdict"])
    MarketComparisonInfo.objects.create(lot=lot, **fixture["market"])

    audit_obj = CrossAuditReport.objects.create(lot=lot, verified_at=now, **fixture["audit"])
    for history_data in fixture.get("audit_history") or []:
        PastAuctionRecord.objects.create(audit=audit_obj, **history_data)

    checklist = SafetyChecklist.objects.create(lot=lot, **fixture["safety"])
    for item_data in fixture.get("safety_items") or []:
        SafetyCheckItem.objects.create(checklist=checklist, **item_data)

    customs_obj = customs_model.objects.create(lot_id=lot.pk, **fixture["customs"])
    CurrencyRatesSnapshot.objects.create(customs_id=customs_obj.pk, **fixture["rates"])

    repair = FarpostRepairSummary.objects.create(lot=lot, **fixture["farpost"])
    for part_data in fixture.get("farpost_parts") or []:
        DamagedPartItem.objects.create(repair=repair, **part_data)
    for work_data in fixture.get("farpost_works") or []:
        ServiceWorkItem.objects.create(repair=repair, **work_data)

    ladder = WiseCostLadder.objects.create(lot=lot, **fixture["wise_cost"])
    for step_data in fixture.get("wise_cost_steps") or []:
        WiseCostStep.objects.create(ladder=ladder, **step_data)


def _seed_full_lot(
    user: User,
    now,
    *,
    lot_fields: dict,
    defects: list[dict] | None = None,
    risk_flags: dict,
    verdict: dict,
    market: dict,
    audit: dict,
    audit_history: list[dict] | None = None,
    safety: dict,
    safety_items: list[dict] | None = None,
    customs: dict,
    rates: dict,
    farpost: dict,
    farpost_parts: list[dict] | None = None,
    farpost_works: list[dict] | None = None,
    wise_cost: dict,
    wise_cost_steps: list[dict] | None = None,
) -> Lot:
    lot = Lot.objects.create(user=user, completed_at=now, **lot_fields)
    fixture = {
        "lot_fields": lot_fields,
        "defects": defects,
        "risk_flags": risk_flags,
        "verdict": verdict,
        "market": market,
        "audit": audit,
        "audit_history": audit_history,
        "safety": safety,
        "safety_items": safety_items,
        "customs": customs,
        "rates": rates,
        "farpost": farpost,
        "farpost_parts": farpost_parts,
        "farpost_works": farpost_works,
        "wise_cost": wise_cost,
        "wise_cost_steps": wise_cost_steps,
    }
    _create_lot_relations(lot, now, fixture=fixture)
    return lot


def _seed_corolla(user: User, now) -> Lot:
    return _seed_full_lot(
        user,
        now,
        lot_fields=_COROLLA_LOT_FIELDS,
        defects=_COROLLA_DEFECTS,
        risk_flags=_COROLLA_RISK_FLAGS,
        verdict=_COROLLA_VERDICT,
        market=_COROLLA_MARKET,
        audit=_COROLLA_AUDIT,
        audit_history=_COROLLA_AUDIT_HISTORY,
        safety=_COROLLA_SAFETY_CHECKLIST,
        safety_items=_COROLLA_SAFETY_ITEMS,
        customs=_COROLLA_CUSTOMS,
        rates=_COROLLA_RATES_SNAPSHOT,
        farpost=_COROLLA_FARPOST_SUMMARY,
        farpost_parts=_COROLLA_FARPOST_PARTS,
        farpost_works=_COROLLA_FARPOST_WORKS,
        wise_cost=_COROLLA_WISE_COST_LADDER,
        wise_cost_steps=_COROLLA_WISE_COST_STEPS,
    )


def _seed_vezel(user: User, now) -> Lot:
    return _seed_full_lot(
        user,
        now,
        lot_fields=_VEZEL_LOT_FIELDS,
        defects=_VEZEL_DEFECTS,
        risk_flags=_VEZEL_RISK_FLAGS,
        verdict=_VEZEL_VERDICT,
        market=_VEZEL_MARKET,
        audit=_VEZEL_AUDIT,
        audit_history=_VEZEL_AUDIT_HISTORY,
        safety=_VEZEL_SAFETY_CHECKLIST,
        safety_items=_VEZEL_SAFETY_ITEMS,
        customs=_VEZEL_CUSTOMS,
        rates=_VEZEL_RATES_SNAPSHOT,
        farpost=_VEZEL_FARPOST_SUMMARY,
        farpost_works=_VEZEL_FARPOST_WORKS,
        wise_cost=_VEZEL_WISE_COST_LADDER,
        wise_cost_steps=_VEZEL_WISE_COST_STEPS,
    )


def _seed_note(user: User, now) -> Lot:
    return _seed_full_lot(
        user,
        now,
        lot_fields=_NOTE_LOT_FIELDS,
        defects=_NOTE_DEFECTS,
        risk_flags=_NOTE_RISK_FLAGS,
        verdict=_NOTE_VERDICT,
        market=_NOTE_MARKET,
        audit=_NOTE_AUDIT,
        audit_history=_NOTE_AUDIT_HISTORY,
        safety=_NOTE_SAFETY_CHECKLIST,
        safety_items=_NOTE_SAFETY_ITEMS,
        customs=_NOTE_CUSTOMS,
        rates=_NOTE_RATES_SNAPSHOT,
        farpost=_NOTE_FARPOST_SUMMARY,
        wise_cost=_NOTE_WISE_COST_LADDER,
        wise_cost_steps=_NOTE_WISE_COST_STEPS,
    )


def seed_starter_lots(user: User) -> None:
    """Create benchmark starter lots for a newly registered user."""
    now = timezone.now()
    _seed_corolla(user, now)
    _seed_vezel(user, now)
    _seed_note(user, now)


@transaction.atomic
def backfill_starter_lots(*, defer_fields=(), customs_model=CustomsCalculation) -> int:
    now = timezone.now()
    repaired = 0
    for fixture in _STARTER_FIXTURES.values():
        fields = fixture["lot_fields"]
        lots = Lot.objects.filter(
            completed_at__isnull=False,
            batch_item__isnull=True,
            verdict_detail__isnull=True,
            make=fields["make"],
            model=fields["model"],
            frame_id=fields["frame_id"],
        )
        for lot in lots.defer(*defer_fields).iterator():
            for field, value in fields.items():
                setattr(lot, field, value)
            lot.save(update_fields=[*fields, "updated_at"])
            _create_lot_relations(lot, now, fixture=fixture, customs_model=customs_model)
            repaired += 1
    return repaired
