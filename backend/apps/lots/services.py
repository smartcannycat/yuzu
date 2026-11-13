import logging
import math
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import connection, transaction
from django.db.models import CharField, Count, F, Max, Value
from django.db.models.functions import Coalesce, Concat
from django.utils import timezone
from django.utils.module_loading import import_string

from apps.core.enums import (
    AgeCorridor,
    AuctionHouse,
    BatchStatus,
    BodyPanel,
    ChecklistItemStatus,
    CrossAuditStatus,
    DriveType,
    DutyCalculationMode,
    FrameIdConfidence,
    FuelType,
    ItemProcessingStatus,
    MascotMood,
    OdometerStatus,
    PowerHpSource,
    RiskLevel,
    SystemKey,
    TaskStep,
    TrafficLightColor,
    WorkType,
)
from apps.core.exceptions import (
    BadRequestProblemError,
    ConflictProblemError,
    NotFoundProblemError,
)
from apps.lots import schemas
from apps.lots.customs import (
    DEFAULT_JAPAN_FOB_JPY,
    CurrencyRatesInput,
    CustomsInput,
    LadderInput,
    build_wise_cost_ladder,
    calculate_customs,
)
from apps.lots.models import (
    Batch,
    BatchItem,
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
from apps.lots.schemas import (
    BatchCreateResponse,
    BatchItemStatus,
    BatchProgressResponse,
    LotSummary,
    MascotState,
)
from apps.users.models import User

logger = logging.getLogger(__name__)

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


def _create_lot_relations(lot: Lot, now, *, fixture: dict) -> None:
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

    customs_obj = CustomsCalculation.objects.create(lot=lot, **fixture["customs"])
    CurrencyRatesSnapshot.objects.create(customs=customs_obj, **fixture["rates"])

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
def backfill_starter_lots() -> int:
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
        for lot in lots.iterator():
            for field, value in fields.items():
                setattr(lot, field, value)
            lot.save(update_fields=[*fields, "updated_at"])
            _create_lot_relations(lot, now, fixture=fixture)
            repaired += 1
    return repaired


_ALLOWED_MIME_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
)
_ALLOWED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"})
_MAX_FILE_SIZE = 15 * 1024 * 1024
_MAX_FILES_PER_UPLOAD = 10
_MAX_FILES_PER_BATCH = 20
_POLL_INTERVAL_MS = 1500
_PIPELINE_STEP_DELAY_SEC = 0.2

_BATCH_TERMINAL_STATUSES = frozenset({BatchStatus.COMPLETED, BatchStatus.FAILED})


def _validate_upload_files(files: list[UploadedFile]) -> None:
    if not files:
        raise BadRequestProblemError(
            "Не выбрано ни одного файла",
            title="Файлы не переданы",
        )
    if len(files) > _MAX_FILES_PER_UPLOAD:
        raise BadRequestProblemError(
            f"Можно загрузить не более {_MAX_FILES_PER_UPLOAD} файлов за один раз",
            title="Превышен лимит файлов",
        )
    for upload in files:
        _validate_single_file(upload)


def _validate_single_file(upload: UploadedFile) -> None:
    name = upload.name or ""
    ext = Path(name).suffix.lower()
    content_type = (upload.content_type or "").lower()
    allowed = content_type in _ALLOWED_MIME_TYPES if content_type else ext in _ALLOWED_EXTENSIONS
    if not allowed:
        raise BadRequestProblemError(
            f"Файл «{name}» имеет недопустимый формат. Разрешены: JPEG, PNG, WEBP, HEIC, HEIF",
            title="Недопустимый формат файла",
        )
    if upload.size is None or upload.size > _MAX_FILE_SIZE:
        raise BadRequestProblemError(
            f"Файл «{name}» превышает максимальный размер {_MAX_FILE_SIZE // (1024 * 1024)} МБ",
            title="Превышен размер файла",
        )


def _next_file_index(batch: Batch) -> int:
    max_index = batch.items.aggregate(max=Max("file_index"))["max"]
    return (max_index if max_index is not None else -1) + 1


@transaction.atomic
def create_batch(user: User, files: list[UploadedFile]) -> BatchCreateResponse:
    _validate_upload_files(files)
    batch = Batch.objects.create(user=user, status=BatchStatus.QUEUED)
    for index, upload in enumerate(files):
        upload.seek(0)
        lot = Lot.objects.create(user=user)
        item = BatchItem.objects.create(
            batch=batch,
            lot=lot,
            file_index=index,
            original_filename=upload.name,
            status=ItemProcessingStatus.QUEUED,
            current_step=TaskStep.GATEKEEPER,
        )
        item.original_file.save(upload.name, upload, save=True)
    transaction.on_commit(
        lambda: threading.Thread(target=run_batch_pipeline, args=(batch.id,), daemon=True).start()
    )
    return BatchCreateResponse(
        batch_id=batch.id,
        total_items=len(files),
        status=batch.status,
        created_at=batch.created_at,
        poll_interval_ms=_POLL_INTERVAL_MS,
    )


@transaction.atomic
def append_batch_items(
    user: User,
    batch_id: uuid.UUID,
    files: list[UploadedFile],
) -> BatchProgressResponse:
    _validate_upload_files(files)
    try:
        batch = Batch.objects.select_for_update().get(id=batch_id, user=user)
    except Batch.DoesNotExist as exc:
        raise NotFoundProblemError(
            "Пачка не найдена",
            title="Пачка не найдена",
        ) from exc
    if batch.status in _BATCH_TERMINAL_STATUSES:
        raise ConflictProblemError(
            "Пачка уже завершена. Откройте новую пачку через POST /api/v1/lots/batches",
            title="Пачка завершена",
        )
    current_count = batch.items.count()
    if current_count + len(files) > _MAX_FILES_PER_BATCH:
        raise BadRequestProblemError(
            f"В одной пачке может быть не более {_MAX_FILES_PER_BATCH} файлов",
            title="Превышен лимит файлов в пачке",
        )
    start_index = _next_file_index(batch)
    for offset, upload in enumerate(files):
        upload.seek(0)
        lot = Lot.objects.create(user=user)
        item = BatchItem.objects.create(
            batch=batch,
            lot=lot,
            file_index=start_index + offset,
            original_filename=upload.name,
            status=ItemProcessingStatus.QUEUED,
            current_step=TaskStep.GATEKEEPER,
        )
        item.original_file.save(upload.name, upload, save=True)
    if batch.status == BatchStatus.PARTIAL_FAILED:
        batch.status = BatchStatus.QUEUED
        batch.save(update_fields=["status", "updated_at"])
        transaction.on_commit(
            lambda: threading.Thread(
                target=run_batch_pipeline, args=(batch.id,), daemon=True
            ).start()
        )
    return get_batch_progress(user, batch_id)


def get_batch_progress(user: User, batch_id: uuid.UUID) -> BatchProgressResponse:
    try:
        batch = Batch.objects.get(id=batch_id, user=user)
    except Batch.DoesNotExist as exc:
        raise NotFoundProblemError(
            "Пачка не найдена",
            title="Пачка не найдена",
        ) from exc
    return _build_batch_progress(batch)


def _build_batch_progress(batch: Batch) -> BatchProgressResponse:
    items = list(batch.items.order_by("file_index").select_related("lot"))
    ready_count = sum(1 for i in items if i.status == ItemProcessingStatus.READY)
    failed_count = sum(1 for i in items if i.status == ItemProcessingStatus.FAILED)
    processed_count = ready_count + failed_count
    return BatchProgressResponse(
        batch_id=batch.id,
        status=batch.status,
        mascot=_build_mascot(batch.status, ready_count, len(items)),
        total_count=len(items),
        processed_count=processed_count,
        ready_count=ready_count,
        failed_count=failed_count,
        items=[_build_item_status(item) for item in items],
    )


def _build_item_status(item: BatchItem) -> BatchItemStatus:
    summary: LotSummary | None = None
    if item.status == ItemProcessingStatus.READY and item.lot is not None and item.lot.make:
        summary = _build_lot_summary(item.lot)
    return BatchItemStatus(
        lot_id=item.lot_id,
        file_index=item.file_index,
        original_filename=item.original_filename,
        preview_title=item.preview_title,
        status=item.status,
        current_step=item.current_step,
        error_message=item.error_message,
        summary=summary,
    )


def _build_lot_summary(lot: Lot) -> LotSummary:
    return LotSummary(
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
        created_at=lot.created_at,
    )


def _build_thumbnail_url(lot: Lot) -> str | None:
    if lot.sheet_thumbnail:
        return lot.sheet_thumbnail.url
    return None


def _build_mascot(status: str, ready_count: int, total_count: int) -> MascotState:
    if status == BatchStatus.COMPLETED:
        return MascotState(
            mood=MascotMood.HAPPY,
            phrase_ru=f"Все лоты готовы! {ready_count}/{total_count}",
            badge_text=f"{ready_count} из {total_count} готово",
        )
    if status == BatchStatus.PARTIAL_FAILED:
        return MascotState(
            mood=MascotMood.CONFUSED,
            phrase_ru=f"Часть листов не распознана. Готово {ready_count}/{total_count}",
            badge_text=f"{ready_count} из {total_count} готово",
        )
    if status == BatchStatus.FAILED:
        return MascotState(
            mood=MascotMood.WARNING,
            phrase_ru="Не удалось обработать листы",
            badge_text=f"0 из {total_count} готово",
        )
    return MascotState(
        mood=MascotMood.THINKING,
        phrase_ru=f"Распознаем лоты... {ready_count}/{total_count}",
        badge_text=f"{ready_count} из {total_count} готово",
    )


def _claim_next_queued_item(batch_id: uuid.UUID) -> BatchItem | None:
    with transaction.atomic():
        item = (
            BatchItem.objects.select_for_update()
            .filter(batch_id=batch_id, status=ItemProcessingStatus.QUEUED)
            .order_by("file_index")
            .first()
        )
        if item is None:
            return None
        item.status = ItemProcessingStatus.PROCESSING
        item.current_step = TaskStep.GATEKEEPER
        item.save(update_fields=["status", "current_step", "updated_at"])
        return item


def _advance_step(item: BatchItem, step: TaskStep) -> None:
    item.current_step = step
    item.save(update_fields=["current_step", "updated_at"])
    time.sleep(_PIPELINE_STEP_DELAY_SEC)


def _fail_item(item: BatchItem, step: TaskStep, message: str) -> None:
    item.status = ItemProcessingStatus.FAILED
    item.current_step = step
    item.error_message = message
    item.save(update_fields=["status", "current_step", "error_message", "updated_at"])


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
        item.lot.completed_at = timezone.now()
        item.lot.save(update_fields=["completed_at", "updated_at"])
    item.save(update_fields=["status", "current_step", "updated_at"])


def _step_gatekeeper(item: BatchItem) -> bool:
    _advance_step(item, TaskStep.GATEKEEPER)
    if not item.original_file or not item.original_file.storage.exists(item.original_file.name):
        _fail_item(item, TaskStep.FAILED, "Файл не найден на диске")
        return False
    return True


def _step_cross_audit(_item: BatchItem) -> bool:
    return True


def _step_drom_market(_item: BatchItem) -> bool:
    return True


def _step_farpost_parts(_item: BatchItem) -> bool:
    return True


def recompute_lot_economics(
    lot: Lot,
    *,
    bid_jpy: int | None = None,
    is_commercial_util: bool | None = None,
    include_repairs: bool | None = None,
    custom_power_hp: int | None = None,
    custom_freight_rub: int | None = None,
) -> None:
    """Recompute customs, Wise Cost Ladder and lot totals via the BE-09 engine.

    Requires the lot to already carry a customs calculation with a currency
    rates snapshot (seeded fixtures or a future BE-05 rates provider); the
    stored age corridor and freight are preserved, everything else is
    recalculated from the engine grids. This is the shared backend for the
    pipeline ``customs_calc`` step and the interactive recalculation.
    """
    customs_model = CustomsCalculation.objects.select_related("rates_snapshot").get(lot=lot)
    rates_model = customs_model.rates_snapshot
    if rates_model is None:
        raise ValueError("Отсутствует снимок курсов валют для расчёта таможни")
    rates = CurrencyRatesInput(
        jpy_rub=rates_model.jpy_rub_bank,
        eur_rub=rates_model.eur_rub_cbrf,
        usd_rub=rates_model.usd_rub_cbrf,
    )

    ladder = WiseCostLadder.objects.get(lot=lot)
    applied_bid_jpy = bid_jpy if bid_jpy is not None else ladder.car_bid_jpy
    bid_rub = math.floor(applied_bid_jpy * rates.jpy_rub + 0.5)
    fob_rub = math.floor(DEFAULT_JAPAN_FOB_JPY * rates.jpy_rub + 0.5)
    freight_rub = (
        custom_freight_rub
        if custom_freight_rub is not None
        else customs_model.freight_vladivostok_rub
    )

    if custom_power_hp is not None:
        lot.power_hp = custom_power_hp
        lot.power_hp_source = PowerHpSource.MANUAL
        lot.is_under_160_hp = custom_power_hp <= 160
        lot.save(update_fields=["power_hp", "power_hp_source", "is_under_160_hp"])

    power_hp = custom_power_hp if custom_power_hp is not None else lot.power_hp
    commercial_util = (
        is_commercial_util if is_commercial_util is not None else customs_model.is_commercial_util
    )
    customs_value_rub = bid_rub + fob_rub + freight_rub

    result = calculate_customs(
        CustomsInput(
            engine_cc=lot.engine_cc,
            fuel_type=lot.fuel_type,
            power_hp=power_hp,
            first_reg_year=lot.first_reg_year,
            first_reg_month=lot.first_reg_month,
            age_corridor=customs_model.age_corridor,
            is_commercial_util=commercial_util,
            customs_value_rub=customs_value_rub,
            freight_rub=freight_rub,
            broker_rub=customs_model.broker_svh_sbkts_rub,
        ),
        rates,
        on_date=timezone.now().date(),
    )

    repairs_included = include_repairs if include_repairs is not None else lot.is_repairs_included
    repair = FarpostRepairSummary.objects.filter(lot=lot).first()
    repair_total_rub = repair.grand_total_repair_rub if repair else 0
    market_price_rub = lot.market_price_rf_rub

    ladder_result = build_wise_cost_ladder(
        LadderInput(
            bid_jpy=applied_bid_jpy,
            rates=rates,
            customs=result,
            market_price_rf_rub=market_price_rub,
            broker_rub=customs_model.broker_svh_sbkts_rub,
            repair_total_rub=repair_total_rub,
            include_repairs=repairs_included,
        )
    )

    with transaction.atomic():
        customs_model.age_corridor = result.age_corridor
        customs_model.duty_calculation_mode = result.duty_calculation_mode
        customs_model.engine_cc = result.engine_cc
        customs_model.duty_rate_eur_per_cc = result.duty_rate_eur_per_cc
        customs_model.effective_duty_pct = result.effective_duty_pct
        customs_model.customs_duty_eur = result.customs_duty_eur
        customs_model.customs_duty_rub = result.customs_duty_rub
        customs_model.is_under_160_hp = result.is_under_160_hp
        customs_model.is_commercial_util = result.is_commercial_util
        customs_model.utilization_fee_rub = result.utilization_fee_rub
        customs_model.customs_clearance_fee_rub = result.customs_clearance_fee_rub
        customs_model.freight_vladivostok_rub = result.freight_vladivostok_rub
        customs_model.broker_svh_sbkts_rub = result.broker_svh_sbkts_rub
        customs_model.meti_sanction_risk = result.meti_sanction_risk
        customs_model.save()

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
        lot.save(
            update_fields=[
                "turnkey_cost_rub",
                "net_benefit_rub",
                "benefit_percentage",
                "is_repairs_included",
                "meti_sanction_risk",
                "updated_at",
            ]
        )


def _step_customs_calc(item: BatchItem) -> bool:
    _advance_step(item, TaskStep.CUSTOMS_CALC)
    lot = item.lot
    if lot is None or not lot.engine_cc or not lot.first_reg_year:
        # Engine inputs arrive from the OCR pipeline; the rates snapshot comes
        # from the currency gateway (BE-05). Recomputation is skipped until
        # both prerequisites are in place for uploaded lots.
        return True
    if not CustomsCalculation.objects.filter(lot=lot).exists():
        return True
    try:
        recompute_lot_economics(lot)
    except Exception:
        logger.exception("Customs recomputation failed for lot %s", lot.pk)
        _fail_item(item, TaskStep.FAILED, "Не удалось рассчитать таможенные платежи")
        return False
    return True


def _step_scoring(item: BatchItem) -> bool:
    _advance_step(item, TaskStep.SCORING)
    return True


def _run_parallel_steps(item: BatchItem, step_fns: list) -> bool:
    with ThreadPoolExecutor(max_workers=len(step_fns)) as pool:
        futures = {pool.submit(fn, item): fn for fn in step_fns}
        for future in as_completed(futures):
            if not future.result():
                pool.shutdown(wait=False, cancel_futures=True)
                return False
    return True


def _process_item(item: BatchItem) -> None:
    if not _step_gatekeeper(item):
        return
    if not settings.LOT_PARSER_BACKEND:
        _fail_item(item, TaskStep.FAILED, "Сервис распознавания не настроен")
        return
    try:
        parser = import_string(settings.LOT_PARSER_BACKEND)()
        rejection = parser.gatekeeper(item)
        if rejection:
            _fail_item(item, TaskStep.FAILED, rejection)
            return
        _advance_step(item, TaskStep.FAST_HEADER_OCR)
        item.preview_title = parser.fast_header(item)
        item.save(update_fields=["preview_title", "updated_at"])
        _advance_step(item, TaskStep.GEMINI_OCR)
        parser.parse(item)
        item.lot.refresh_from_db()
        if not item.lot.make or not item.lot.model:
            _fail_item(item, TaskStep.FAILED, "Распознавание не вернуло марку и модель")
            return
    except Exception:
        logger.exception("Parser failed for batch item %s", item.pk)
        _fail_item(item, TaskStep.FAILED, "Не удалось распознать аукционный лист")
        return
    _advance_step(item, TaskStep.CROSS_AUDIT)
    if not _run_parallel_steps(
        item,
        [_step_cross_audit, _step_drom_market, _step_farpost_parts],
    ):
        return
    if not _step_customs_calc(item):
        return
    if not _step_scoring(item):
        return
    if item.lot is None:
        _fail_item(item, TaskStep.FAILED, "Лот не привязан к элементу пачки")
        return
    missing = _missing_summary_fields(item.lot)
    if missing:
        _fail_item(
            item,
            TaskStep.FAILED,
            f"Недостаточно данных для карточки лота: {', '.join(missing)}",
        )
        return
    item.lot.refresh_from_db()
    if not _has_full_detail(item.lot):
        _fail_item(
            item,
            TaskStep.FAILED,
            "Недостаточно данных для детальной карточки лота",
        )
        return
    _complete_item(item)


def _finalize_batch_locked(batch: Batch) -> None:
    items = list(batch.items.all())
    total = len(items)
    ready = sum(1 for i in items if i.status == ItemProcessingStatus.READY)
    failed = sum(1 for i in items if i.status == ItemProcessingStatus.FAILED)
    if total == 0:
        status = BatchStatus.FAILED
    elif ready == total:
        status = BatchStatus.COMPLETED
    elif failed == total:
        status = BatchStatus.FAILED
    else:
        status = BatchStatus.PARTIAL_FAILED
    batch.status = status
    batch.save(update_fields=["status", "updated_at"])


def run_batch_pipeline(batch_id: uuid.UUID) -> None:
    try:
        with transaction.atomic():
            batch = Batch.objects.select_for_update().get(id=batch_id)
            if batch.status != BatchStatus.QUEUED:
                return
            batch.status = BatchStatus.PROCESSING
            batch.save(update_fields=["status", "updated_at"])
        while True:
            item = _claim_next_queued_item(batch_id)
            if item is not None:
                _process_item(item)
                continue
            with transaction.atomic():
                batch = Batch.objects.select_for_update().get(id=batch_id)
                if batch.items.filter(status=ItemProcessingStatus.QUEUED).exists():
                    continue
                _finalize_batch_locked(batch)
                break
    except Exception:
        logger.exception("Batch pipeline failed for %s", batch_id)
        with transaction.atomic():
            batch = Batch.objects.select_for_update().get(id=batch_id)
            batch.items.filter(
                status__in=(ItemProcessingStatus.QUEUED, ItemProcessingStatus.PROCESSING)
            ).update(
                status=ItemProcessingStatus.FAILED,
                current_step=TaskStep.FAILED,
                error_message="Не удалось обработать аукционный лист",
                updated_at=timezone.now(),
            )
            _finalize_batch_locked(batch)
    finally:
        connection.close()


def recover_batches_on_startup() -> None:
    import sys

    if "pytest" in sys.modules:
        return
    stuck_statuses = [BatchStatus.QUEUED, BatchStatus.PROCESSING]
    batches = Batch.objects.filter(status__in=stuck_statuses)
    for batch in batches:
        BatchItem.objects.filter(
            batch=batch,
            status=ItemProcessingStatus.PROCESSING,
        ).update(
            status=ItemProcessingStatus.QUEUED,
            current_step=TaskStep.GATEKEEPER,
        )
        Batch.objects.filter(id=batch.id).update(status=BatchStatus.QUEUED)
        threading.Thread(target=run_batch_pipeline, args=(batch.id,), daemon=True).start()


_SORT_FIELD_MAP: dict[str, str] = {
    "created_at": "created_at",
    "net_benefit": "net_benefit_rub",
    "turnkey_cost": "turnkey_cost_rub",
}

_ACTIVE_BATCH_STATUSES = frozenset({BatchStatus.QUEUED, BatchStatus.PROCESSING})
_PROCESSING_ITEM_STATUSES = frozenset(
    {ItemProcessingStatus.QUEUED, ItemProcessingStatus.PROCESSING}
)

_DEFAULT_PAGE = 1
_DEFAULT_PAGE_SIZE = 20

_DETAIL_RELATED_FIELDS = (
    "risk_flags",
    "verdict_detail",
    "market_info",
    "cross_audit",
    "safety_checklist",
    "customs_calc",
    "customs_calc__rates_snapshot",
    "farpost_repair",
    "wise_cost_ladder",
)

_DETAIL_PREFETCH_FIELDS = (
    "defects",
    "cross_audit__anomalies",
    "cross_audit__history",
    "safety_checklist__items",
    "farpost_repair__parts",
    "farpost_repair__service_works",
    "wise_cost_ladder__steps",
)


def _apply_search(qs, query: str | None):
    query = query.strip() if query else ""
    if not query:
        return qs
    return qs.annotate(
        _search=Concat(
            Coalesce(F("make"), Value("")),
            Value(" "),
            Coalesce(F("model"), Value("")),
            Value(" "),
            Coalesce(F("frame_id"), Value("")),
            Value(" "),
            Coalesce(F("lot_number"), Value("")),
            Value(" "),
            Coalesce(F("auction_house"), Value("")),
            Value(" "),
            Coalesce(F("verdict_headline"), Value("")),
            output_field=CharField(),
        ),
    ).filter(_search__icontains=query)


def _apply_filters(
    qs,
    *,
    make: str | None,
    model: str | None,
    verdict: TrafficLightColor | None,
    has_anomaly: bool | None,
):
    if make:
        qs = qs.filter(make__iexact=make)
    if model:
        qs = qs.filter(model__iexact=model)
    if verdict:
        qs = qs.filter(verdict=verdict)
    if has_anomaly is not None:
        qs = qs.filter(has_anomaly=has_anomaly)
    return qs


def _apply_sorting(qs, *, sort_by: str, sort_order: str):
    field = _SORT_FIELD_MAP[sort_by]
    return qs.order_by(field if sort_order == "asc" else f"-{field}", "pk")


def _facet_counts(qs, field: str) -> list[schemas.FilterCountItem]:
    rows = (
        qs.exclude(**{f"{field}__isnull": True})
        .exclude(**{f"{field}": ""})
        .values(field)
        .annotate(count=Count("id"))
        .order_by("-count", field)
    )
    return [schemas.FilterCountItem(value=row[field], count=row["count"]) for row in rows]


def _build_available_filters(
    *,
    make_facet_qs,
    model_facet_qs,
    verdict_facet_qs,
) -> schemas.AvailableFilters:
    return schemas.AvailableFilters(
        total_lots_count=make_facet_qs.count(),
        makes=_facet_counts(make_facet_qs, "make"),
        models=_facet_counts(model_facet_qs, "model"),
        counts_by_verdict={
            row["verdict"]: row["count"]
            for row in verdict_facet_qs.exclude(verdict__isnull=True)
            .exclude(verdict="")
            .values("verdict")
            .annotate(count=Count("id"))
        },
    )


def _build_in_progress_item(item: BatchItem) -> schemas.InProgressItemPreview:
    return schemas.InProgressItemPreview(
        batch_id=item.batch_id,
        lot_id=item.lot_id,
        display_title=item.preview_title or item.original_filename,
        status=item.status,
        current_step=item.current_step,
    )


def _build_in_progress(user: User) -> schemas.InProgressSummary:
    active_batches_count = Batch.objects.filter(
        user=user,
        status__in=_ACTIVE_BATCH_STATUSES,
    ).count()
    items = list(
        BatchItem.objects.filter(
            batch__user=user,
            batch__status__in=_ACTIVE_BATCH_STATUSES,
            status__in=_PROCESSING_ITEM_STATUSES,
        )
        .select_related("batch")
        .order_by("-batch__created_at", "file_index"),
    )
    return schemas.InProgressSummary(
        active_batches_count=active_batches_count,
        total_processing_lots=len(items),
        items=[_build_in_progress_item(item) for item in items],
    )


def get_lots_list(
    user: User,
    *,
    query: str | None = None,
    make: str | None = None,
    model: str | None = None,
    verdict: TrafficLightColor | None = None,
    has_anomaly: bool | None = None,
    page: int = _DEFAULT_PAGE,
    page_size: int = _DEFAULT_PAGE_SIZE,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> schemas.LotListResponse:
    base_qs = Lot.objects.filter(user=user, completed_at__isnull=False)
    searched = _apply_search(base_qs, query)
    if has_anomaly is not None:
        searched = searched.filter(has_anomaly=has_anomaly)

    make_facet_qs = _apply_filters(
        searched, make=None, model=None, verdict=verdict, has_anomaly=None
    )
    model_facet_qs = _apply_filters(
        searched, make=make, model=None, verdict=verdict, has_anomaly=None
    )
    verdict_facet_qs = _apply_filters(
        searched, make=make, model=model, verdict=None, has_anomaly=None
    )

    filtered = _apply_filters(searched, make=make, model=model, verdict=verdict, has_anomaly=None)
    sorted_qs = _apply_sorting(filtered, sort_by=sort_by, sort_order=sort_order)

    total_items = sorted_qs.count()
    total_pages = math.ceil(total_items / page_size) if total_items else 0
    offset = (page - 1) * page_size
    page_lots = list(sorted_qs[offset : offset + page_size])

    return schemas.LotListResponse(
        items=[_build_lot_summary(lot) for lot in page_lots],
        in_progress=_build_in_progress(user),
        pagination=schemas.PaginationMeta(
            total_items=total_items,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
        available_filters=_build_available_filters(
            make_facet_qs=make_facet_qs,
            model_facet_qs=model_facet_qs,
            verdict_facet_qs=verdict_facet_qs,
        ),
    )


def _has_full_detail(lot: Lot) -> bool:
    required_attrs = (
        "risk_flags",
        "verdict_detail",
        "market_info",
        "cross_audit",
        "safety_checklist",
        "customs_calc",
        "farpost_repair",
        "wise_cost_ladder",
    )
    if not all(hasattr(lot, name) for name in required_attrs):
        return False
    return hasattr(lot.customs_calc, "rates_snapshot")


def _build_normalized_sheet(lot: Lot) -> schemas.NormalizedSheet:
    return schemas.NormalizedSheet(
        lot_number=lot.lot_number,
        auction_house=lot.auction_house,
        auction_branch=lot.auction_branch,
        auction_strictness_index=lot.auction_strictness_index,
        make=lot.make,
        model=lot.model,
        trim=lot.trim,
        model_code=lot.model_code,
        chassis_number=lot.chassis_number,
        frame_id=lot.frame_id,
        frame_id_confidence=lot.frame_id_confidence,
        first_reg_year=lot.first_reg_year,
        first_reg_month=lot.first_reg_month,
        first_reg_date_str=lot.first_reg_date_str,
        is_pass_corridor_3_5=lot.is_pass_corridor_3_5,
        engine_cc=lot.engine_cc,
        power_hp=lot.power_hp,
        power_hp_source=lot.power_hp_source,
        is_under_160_hp=lot.is_under_160_hp,
        mileage_km=lot.mileage_km,
        odometer_status=lot.odometer_status,
        transmission=lot.transmission,
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


def _build_lot_detail(lot: Lot) -> schemas.LotDetailResponse:
    return schemas.LotDetailResponse(
        lot_id=lot.id,
        created_at=lot.created_at,
        updated_at=lot.updated_at,
        passport=_build_normalized_sheet(lot),
        verdict=schemas.TrafficLightVerdict.model_validate(lot.verdict_detail),
        market=schemas.MarketComparisonInfo.model_validate(lot.market_info),
        audit=_build_audit_out(lot.cross_audit),
        safety_checklist=_build_safety_out(lot.safety_checklist),
        economics=_build_economics(lot),
        media=_build_media_links(lot),
    )


def get_lot_detail(user: User, lot_id: uuid.UUID) -> schemas.LotDetailResponse:
    try:
        lot = (
            Lot.objects.select_related(*_DETAIL_RELATED_FIELDS)
            .prefetch_related(*_DETAIL_PREFETCH_FIELDS)
            .get(id=lot_id, user=user, completed_at__isnull=False)
        )
    except Lot.DoesNotExist as exc:
        raise NotFoundProblemError(
            "Лот не найден",
            title="Лот не найден",
        ) from exc
    if not _has_full_detail(lot):
        raise NotFoundProblemError(
            "Детальная спецификация лота ещё не готова",
            title="Лот не найден",
        )
    return _build_lot_detail(lot)
