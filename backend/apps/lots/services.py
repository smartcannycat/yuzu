from django.utils import timezone

from apps.core.enums import (
    AuctionHouse,
    DriveType,
    FrameIdConfidence,
    FuelType,
    OdometerStatus,
    PowerHpSource,
    TrafficLightColor,
)
from apps.lots.models import Lot
from apps.users.models import User

_STARTER_LOTS_DATA: list[dict] = [
    {
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
    },
    {
        "make": "Honda",
        "model": "Vezel",
        "year": 2019,
        "frame_id": "RU3-1209412",
        "chassis_number": "RU3-1209412",
        "auction_house": AuctionHouse.USS,
        "overall_grade": "4.0",
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
        "year": 2021,
        "frame_id": "HE12-389104",
        "chassis_number": "HE12-389104",
        "overall_grade": "4.5",
        "turnkey_cost_rub": 980000,
        "market_price_rf_rub": 1190000,
        "net_benefit_rub": 210000,
        "benefit_percentage": 21.4,
        "verdict": TrafficLightColor.GREEN,
        "verdict_headline": "🟢 РЕКОМЕНДОВАНО К ПОКУПКЕ",
        "has_anomaly": False,
    },
]


def seed_starter_lots(user: User) -> None:
    """Create benchmark starter lots for a newly registered user."""
    now = timezone.now()
    for lot_data in _STARTER_LOTS_DATA:
        Lot.objects.create(user=user, completed_at=now, **lot_data)
