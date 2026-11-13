from datetime import date
from typing import Any

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

_DEFAULT_RISK_FLAGS: dict[str, bool] = dict.fromkeys(
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

_DEFAULT_RATES_SNAPSHOT: dict[str, Any] = {
    "jpy_rub_bank": 0.585,
    "jpy_rate_source": "ДВ-банк (ориентир)",
    "eur_rub_cbrf": 95.0,
    "usd_rub_cbrf": 85.0,
    "cbrf_date": "12.11.2026",
}

_DEFAULT_AUDIT: dict[str, Any] = {
    "status": CrossAuditStatus.CLEAN,
    "source_name": "AucJP + AAA Japan / Pravto",
    "is_archive_available": True,
    "risk_level": RiskLevel.CLEAN,
    "has_critical_anomaly": False,
    "headline_ru": "Аудит истории торгов: нарушений по Frame ID не обнаружено",
    "times_auctioned": 1,
}

_DEFAULT_SAFETY_CHECKLIST: dict[str, Any] = {
    "overall_status": ChecklistItemStatus.OK,
    "overall_label_ru": "В норме",
}

_WISE_COST_TEMPLATE: tuple[tuple[int, str, str, bool], ...] = (
    (1, "Ставка на аукционе", "JPY", False),
    (2, "Расходы в Японии (FOB и сбор)", "JPY", False),
    (3, "Фрахт Тояма-ВЛК", "USD", False),
    (4, "Таможенная пошлина ЕАЭС и сбор", "EUR", False),
    (5, "Утилизационный сбор РФ", "RUB", False),
    (6, "СВХ, брокер, СБКТС, ЭПТС", "RUB", False),
    (7, "Запчасти Farpost и ремонт", "RUB", True),
)


def _build_safety_items(
    engine_detail_ru: str,
    frame_detail_ru: str = "Нарушений геометрии и ремонта несущих элементов не отмечено",
) -> list[dict[str, Any]]:
    rows = (
        (SystemKey.STRUCTURAL_FRAME, "Силовой каркас и лонжероны", frame_detail_ru),
        (
            SystemKey.AIRBAGS_SRS,
            "Подушки безопасности (SRS)",
            "Отметок о срабатывании или отсутствии подушек нет",
        ),
        (SystemKey.ENGINE_TRANSMISSION, "ДВС и трансмиссия", engine_detail_ru),
        (SystemKey.UNDERBODY_CORROSION, "Днище и пороги", "Сквозная коррозия не отмечена"),
        (
            SystemKey.FLOOD_OR_FIRE,
            "Следы затопления / пожара / града",
            "Стоп-факторов в бланке не зафиксировано",
        ),
    )
    return [
        {"system_key": key, "label_ru": label, "status": ChecklistItemStatus.OK, "detail_ru": desc}
        for key, label, desc in rows
    ]


def _defect(
    panel_id: BodyPanel,
    panel_ru: str,
    raw_code: str,
    description_ru: str,
) -> dict[str, Any]:
    dtype = raw_code.rstrip("0123456789")
    sev_digits = raw_code[len(dtype) :]
    return {
        "panel_id": panel_id,
        "panel_ru": panel_ru,
        "defect_types": [dtype],
        "severity": int(sev_digits) if sev_digits else None,
        "raw_code": raw_code,
        "description_ru": description_ru,
    }


def _work(
    work_type: WorkType,
    label_ru: str,
    amount_rub: int,
    zero_cost_reason_ru: str | None = None,
) -> dict[str, Any]:
    return {
        "work_type": work_type,
        "label_ru": label_ru,
        "amount_rub": amount_rub,
        "zero_cost_reason_ru": zero_cost_reason_ru,
    }


def _build_fixture(
    *,
    lot_fields: dict[str, Any],
    defects: list[dict[str, Any]],
    risk_overrides: dict[str, bool] | None = None,
    headline: str,
    badge_text: str,
    body_summary_ru: str,
    interior_summary_ru: str,
    reasoning_bullets: list[str],
    market_stats: tuple[int, int, int, int, str],
    audit_meta: tuple[date, str, int],
    safety_items: list[dict[str, Any]],
    customs_overrides: dict[str, Any],
    farpost_totals: tuple[int, int, bool],
    farpost_parts: list[dict[str, Any]] | None = None,
    farpost_works: list[dict[str, Any]] | None = None,
    step_amounts: list[tuple[int, float]],
) -> dict[str, Any]:
    analogs_count, p_min, p_max, filtered_out, drom_url = market_stats
    auction_date, defects_summary, closing_jpy = audit_meta
    parts_rub, works_rub, color_matched = farpost_totals
    bid_rub, bid_jpy = step_amounts[0]

    return {
        "lot_fields": lot_fields,
        "defects": defects,
        "risk_flags": {**_DEFAULT_RISK_FLAGS, **(risk_overrides or {})},
        "verdict": {
            "verdict": lot_fields["verdict"],
            "headline": headline,
            "short_verdict_label": lot_fields["verdict_headline"],
            "badge_text": badge_text,
            "net_benefit_rub": lot_fields["net_benefit_rub"],
            "benefit_percentage": lot_fields["benefit_percentage"],
            "body_summary_ru": body_summary_ru,
            "interior_summary_ru": interior_summary_ru,
            "reasoning_bullets": reasoning_bullets,
        },
        "market": {
            "market_price_rf_rub": lot_fields["market_price_rf_rub"],
            "analogs_count": analogs_count,
            "price_min_rub": p_min,
            "price_max_rub": p_max,
            "search_region_ru": "ДФО / Владивосток",
            "excludes_under_order": True,
            "filtered_out_under_order_count": filtered_out,
            "is_fallback": False,
            "fallback_reason_ru": None,
            "drom_search_url": drom_url,
        },
        "audit": _DEFAULT_AUDIT,
        "audit_history": [
            {
                "auction_date": auction_date,
                "auction_house": lot_fields["auction_branch"],
                "auction_strictness": lot_fields["auction_strictness_index"],
                "lot_number": lot_fields["lot_number"],
                "overall_grade": lot_fields["overall_grade"],
                "mileage_km": lot_fields["mileage_km"],
                "defects_summary": defects_summary,
                "closing_price_jpy": closing_jpy,
                "sheet_archive_url": None,
            }
        ],
        "safety": _DEFAULT_SAFETY_CHECKLIST,
        "safety_items": safety_items,
        "customs": {
            "age_corridor": AgeCorridor.THREE_TO_FIVE_YEARS,
            "duty_calculation_mode": DutyCalculationMode.EUR_PER_CC,
            "engine_cc": lot_fields["engine_cc"],
            "duty_rate_eur_per_cc": 1.7,
            "effective_duty_pct": None,
            "is_under_160_hp": True,
            "is_commercial_util": False,
            "utilization_fee_rub": 5200,
            "customs_clearance_fee_rub": 3120,
            "meti_sanction_risk": lot_fields["meti_sanction_risk"],
            **customs_overrides,
        },
        "rates": _DEFAULT_RATES_SNAPSHOT,
        "farpost": {
            "total_parts_from_rub": parts_rub,
            "total_works_rub": works_rub,
            "grand_total_repair_rub": parts_rub + works_rub,
            "has_color_matched_parts": color_matched,
            "included_in_turnkey_hint_ru": "Сумма уже включена в расчёт под ключ",
        },
        "farpost_parts": farpost_parts or [],
        "farpost_works": farpost_works or [],
        "wise_cost": {
            "car_bid_jpy": int(bid_jpy),
            "car_bid_rub": bid_rub,
            "turnkey_cost_rub": lot_fields["turnkey_cost_rub"],
            "market_price_rf_rub": lot_fields["market_price_rf_rub"],
            "net_benefit_rub": lot_fields["net_benefit_rub"],
            "benefit_percentage": lot_fields["benefit_percentage"],
        },
        "wise_cost_steps": [
            {
                "step_number": num,
                "name_ru": name,
                "amount_rub": amt_rub,
                "original_currency": curr,
                "original_amount": float(orig_amt),
                "is_optional": opt,
            }
            for (num, name, curr, opt), (amt_rub, orig_amt) in zip(
                _WISE_COST_TEMPLATE, step_amounts, strict=True
            )
        ],
    }


_COROLLA_FIXTURE = _build_fixture(
    lot_fields={
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
        "seller_comments_ru": ["Один владелец, сервисная книжка в наличии"],
        "year": 2020,
        "turnkey_cost_rub": 1104899,
        "market_price_rf_rub": 1520000,
        "net_benefit_rub": 415101,
        "benefit_percentage": 37.6,
        "verdict": TrafficLightColor.GREEN,
        "verdict_headline": "🟢 РЕКОМЕНДОВАНО К ПОКУПКЕ",
        "meti_sanction_risk": False,
        "has_anomaly": False,
    },
    defects=[
        _defect(
            BodyPanel.FRONT_LEFT_DOOR,
            "Передняя левая дверь",
            "XX",
            "Передняя левая дверь — замена (в цвет 070)",
        ),
        _defect(
            BodyPanel.FRONT_LEFT_FENDER,
            "Арка переднего крыла",
            "A2",
            "Арка переднего крыла — царапина до 10 см",
        ),
        _defect(
            BodyPanel.LEFT_SILL,
            "Левый порог",
            "U2",
            "Порог — мелкая вмятина (PDR без покраски)",
        ),
        _defect(
            BodyPanel.REAR_LEFT_DOOR,
            "Задняя левая дверь",
            "W1",
            "Задняя левая дверь — вторичный заводской окрас",
        ),
    ],
    risk_overrides={"panel_replaced_xx": True},
    headline="РЕКОМЕНДОВАНО К ПОКУПКЕ",
    badge_text="Выгода: +415 101 ₽",
    body_summary_ru=(
        "Кузов (оценка C): замена левой двери (XX), "
        "деталь найдена на Farpost в цвет за от 18 000 ₽."
    ),
    interior_summary_ru=(
        "Салон (оценка B): чистый, без прокуров, мелкие естественные следы эксплуатации."
    ),
    reasoning_bullets=[
        "Строгий аукцион TAA Chubu: оценка 3.5 C/B, родной пробег 58 240 км",
        "Несущий каркас и подушки SRS целы, повреждены только навесные панели",
        "Льготный утильсбор (5 200 ₽) и проходной коридор ЕАЭС 3-5 лет",
    ],
    market_stats=(
        14,
        1390000,
        1680000,
        6,
        "https://vladivostok.drom.ru/toyota/corolla_touring/year-2020/engine-1.2/manual/",
    ),
    audit_meta=(
        date(2026, 11, 12),
        "Замена двери XX, окрас задней двери W1, царапина A2",
        1060000,
    ),
    safety_items=_build_safety_items(
        "Замечаний инспектора по работе 1.2T и 6MT в бланке нет",
        frame_detail_ru="Нарушений геометрии, ремонта стоек и рамки радиатора на листе не отмечено",
    ),
    customs_overrides={
        "customs_duty_eur": 2033.2,
        "customs_duty_rub": 193154,
        "freight_vladivostok_rub": 97750,
        "broker_svh_sbkts_rub": 99000,
    },
    farpost_totals=(18000, 13000, True),
    farpost_parts=[
        {
            "panel_id": BodyPanel.FRONT_LEFT_DOOR,
            "defect_code": "XX",
            "part_name_ru": "Передняя левая дверь",
            "subtitle_ru": "контрактная деталь в заводской цвет 070",
            "price_from_rub": 18000,
            "in_stock_vladivostok": True,
            "is_statistical_fallback": False,
        }
    ],
    farpost_works=[
        _work(WorkType.MOUNT_DISMOUNT, "Снятие и монтаж двери", 4000),
        _work(WorkType.PAINT, "Покраска двери (в цвет 070)", 0, "не требуется"),
        _work(WorkType.PDR_AND_POLISH, "PDR удаление вмятины + полировка", 9000),
    ],
    step_amounts=[
        (620100, 1060000.0),
        (55575, 95000.0),
        (97750, 1150.0),
        (196274, 2033.2),
        (5200, 5200.0),
        (99000, 99000.0),
        (31000, 31000.0),
    ],
)

_VEZEL_FIXTURE = _build_fixture(
    lot_fields={
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
        "inspector_notes_raw": ["前バンパー A2 / 後ドア U2"],
        "seller_comments_ru": ["Один владелец, не курили в салоне"],
        "year": 2022,
        "turnkey_cost_rub": 1480000,
        "market_price_rf_rub": 1600000,
        "net_benefit_rub": 120000,
        "benefit_percentage": 8.1,
        "verdict": TrafficLightColor.YELLOW,
        "verdict_headline": "🟡 ВНИМАНИЕ: СКОЛЫ A2/U2",
        "meti_sanction_risk": True,
        "has_anomaly": False,
    },
    defects=[
        _defect(
            BodyPanel.FRONT_BUMPER,
            "Передний бампер",
            "A2",
            "Передний бампер — сколы до 10 см",
        ),
        _defect(
            BodyPanel.REAR_LEFT_DOOR,
            "Задняя левая дверь",
            "U2",
            "Задняя левая дверь — вмятина (PDR без покраски)",
        ),
    ],
    headline="ВНИМАНИЕ: СКОЛЫ A2/U2",
    badge_text="Выгода: +120 000 ₽",
    body_summary_ru=(
        "Кузов (оценка A): сколы A2 на бампере и вмятина U2 на двери, "
        "ремонт PDR без замены деталей."
    ),
    interior_summary_ru="Салон (оценка A): чистый, без замечаний.",
    reasoning_bullets=[
        "Гибрид Honda Vezel: санкционный риск METI, но мощность 131 л.с. < 160 л.с.",
        "Оценка 4.0 A/A, родной пробег 45 000 км",
        "Ремонт ограничен сколами и вмятинами без замены панелей",
    ],
    market_stats=(
        8,
        1450000,
        1850000,
        4,
        "https://vladivostok.drom.ru/honda/vezel/year-2022/engine-1.5/4wd/",
    ),
    audit_meta=(
        date(2026, 11, 11),
        "Сколы A2 на бампере, вмятина U2 на двери",
        1700000,
    ),
    safety_items=_build_safety_items("Гибридная установка i-MMD без замечаний инспектора"),
    customs_overrides={
        "customs_duty_eur": 2517.68,
        "customs_duty_rub": 239180,
        "freight_vladivostok_rub": 95000,
        "broker_svh_sbkts_rub": 65000,
    },
    farpost_totals=(0, 18000, False),
    farpost_works=[
        _work(WorkType.PDR_AND_POLISH, "PDR удаление вмятины + полировка сколов", 18000),
    ],
    step_amounts=[
        (994500, 1700000.0),
        (60000, 102500.0),
        (95000, 1117.0),
        (242300, 2517.68),
        (5200, 5200.0),
        (65000, 65000.0),
        (18000, 18000.0),
    ],
)

_NOTE_FIXTURE = _build_fixture(
    lot_fields={
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
        "inspector_notes_raw": ["前フェンダー W1"],
        "seller_comments_ru": ["Первый владелец, сервисная история доступна"],
        "year": 2024,
        "turnkey_cost_rub": 980000,
        "market_price_rf_rub": 1190000,
        "net_benefit_rub": 210000,
        "benefit_percentage": 21.4,
        "verdict": TrafficLightColor.GREEN,
        "verdict_headline": "🟢 РЕКОМЕНДОВАНО К ПОКУПКЕ",
        "meti_sanction_risk": True,
        "has_anomaly": False,
    },
    defects=[
        _defect(
            BodyPanel.FRONT_LEFT_FENDER,
            "Переднее левое крыло",
            "W1",
            "Переднее левое крыло — мелкий вторичный окрас",
        ),
    ],
    headline="РЕКОМЕНДОВАНО К ПОКУПКЕ",
    badge_text="Выгода: +210 000 ₽",
    body_summary_ru="Кузов (оценка A): только мелкий вторичный окрас W1 на переднем крыле.",
    interior_summary_ru="Салон (оценка A): новый, без следов эксплуатации.",
    reasoning_bullets=[
        "Nissan Note e-Power: гибрид, санкционный риск METI, но 109 л.с. < 160 л.с.",
        "Оценка 4.5 A/A, родной пробег 65 000 км",
        "Льготный утильсбор и коридор до 3 лет, ремонт не требуется",
    ],
    market_stats=(
        6,
        1090000,
        1390000,
        3,
        "https://vladivostok.drom.ru/nissan/note/year-2024/engine-1.2/",
    ),
    audit_meta=(
        date(2026, 11, 10),
        "Мелкий вторичный окрас W1 на переднем крыле",
        1200000,
    ),
    safety_items=_build_safety_items("Гибридная установка e-Power без замечаний инспектора"),
    customs_overrides={
        "age_corridor": AgeCorridor.UNDER_3_YEARS,
        "duty_calculation_mode": DutyCalculationMode.PCT_OF_VALUE,
        "duty_rate_eur_per_cc": None,
        "effective_duty_pct": 48.0,
        "customs_duty_eur": 576.0,
        "customs_duty_rub": 54720,
        "customs_clearance_fee_rub": 3100,
        "freight_vladivostok_rub": 90000,
        "broker_svh_sbkts_rub": 27980,
    },
    farpost_totals=(0, 0, False),
    step_amounts=[
        (702000, 1200000.0),
        (97000, 165800.0),
        (90000, 1058.0),
        (57820, 576.0),
        (5200, 5200.0),
        (27980, 27980.0),
        (0, 0.0),
    ],
)

_STARTER_FIXTURES: dict[tuple[str, str], dict[str, Any]] = {
    (fixture["lot_fields"]["make"], fixture["lot_fields"]["model"]): fixture
    for fixture in (_COROLLA_FIXTURE, _VEZEL_FIXTURE, _NOTE_FIXTURE)
}


def _create_lot_relations(
    lot: Lot,
    now,
    *,
    fixture: dict[str, Any],
    customs_model=CustomsCalculation,
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

    customs_obj = customs_model.objects.create(lot=lot, **fixture["customs"])
    if customs_model is CustomsCalculation:
        CurrencyRatesSnapshot.objects.create(customs=customs_obj, **fixture["rates"])
    else:
        CurrencyRatesSnapshot.objects.create(customs_id=customs_obj.pk, **fixture["rates"])

    repair = FarpostRepairSummary.objects.create(lot=lot, **fixture["farpost"])
    for part_data in fixture.get("farpost_parts") or []:
        DamagedPartItem.objects.create(repair=repair, **part_data)
    for work_data in fixture.get("farpost_works") or []:
        ServiceWorkItem.objects.create(repair=repair, **work_data)

    ladder = WiseCostLadder.objects.create(lot=lot, **fixture["wise_cost"])
    for step_data in fixture.get("wise_cost_steps") or []:
        WiseCostStep.objects.create(ladder=ladder, **step_data)


def _seed_lot_from_fixture(user: User, now, fixture: dict[str, Any]) -> Lot:
    lot = Lot.objects.create(user=user, completed_at=now, **fixture["lot_fields"])
    _create_lot_relations(lot, now, fixture=fixture)
    return lot


def seed_starter_lots(user: User) -> None:
    """Create benchmark starter lots for a newly registered user."""
    now = timezone.now()
    for fixture in _STARTER_FIXTURES.values():
        _seed_lot_from_fixture(user, now, fixture)


@transaction.atomic
def backfill_starter_lots(*, defer_fields=(), customs_model=CustomsCalculation) -> int:
    """Repair legacy starter lots missing related detail records."""
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
            _create_lot_relations(
                lot,
                now,
                fixture=fixture,
                customs_model=customs_model,
            )
            repaired += 1
    return repaired
