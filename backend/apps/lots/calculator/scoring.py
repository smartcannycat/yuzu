"""Traffic light scoring: verdict computation from lot economics and risks.

Thresholds follow the canonical contract (docs/API_DATA_CONTRACTS.md):
- GREEN: net benefit >= 150k RUB and no critical risk factors.
- YELLOW: net benefit in 50k..150k, or cosmetic issues (windshield damage,
  repaint, replaced panels, color change).
- RED: stop factors (flood, airbags, corrosion, frame repair, odometer
  tampering, repaired grade R/RA), METI export sanction risk, or net
  benefit < 50k.
"""

import logging

from django.db import transaction

from apps.core.enums import OdometerStatus, TrafficLightColor
from apps.lots.models import Lot, LotRiskFlags, TrafficLightVerdict

logger = logging.getLogger(__name__)

GREEN_BENEFIT_MIN_RUB = 150_000
YELLOW_BENEFIT_MIN_RUB = 50_000

# Risk flag names split by severity (LotRiskFlags boolean fields).
_CRITICAL_RISK_FIELDS: tuple[str, ...] = (
    "is_flooded",
    "airbag_deployed",
    "underbody_corrosion",
    "core_support_repair",
    "pillar_or_frame_repair",
    "odometer_issue",
    "repaired_grade_r_ra",
)
_WARNING_RISK_FIELDS: tuple[str, ...] = (
    "hail_damage",
    "underbody_rust",
    "panel_needs_replacement_x",
    "windshield_damage",
    # Cosmetic defects downgrade the verdict to yellow per the contract
    # ("benefit 50k..150k, or cosmetic defects").
    "panel_replaced_xx",
    "color_changed",
)

_RISK_LABELS_RU: dict[str, str] = {
    "is_flooded": "следы затопления",
    "airbag_deployed": "сработавшие подушки безопасности",
    "underbody_corrosion": "сквозная коррозия",
    "core_support_repair": "ремонт рамки радиатора",
    "pillar_or_frame_repair": "ремонт силовой структуры",
    "odometer_issue": "проблемы с одометром",
    "repaired_grade_r_ra": "аварийный статус (R/RA)",
    "hail_damage": "градобой",
    "underbody_rust": "поверхностная ржавчина",
    "panel_needs_replacement_x": "детали под замену",
    "windshield_damage": "повреждение лобового стекла",
    "panel_replaced_xx": "заменённые элементы",
    "color_changed": "смена цвета",
}


def collect_risk_factors(lot: Lot) -> tuple[list[str], list[str]]:
    """Return (critical, warning) Russian labels of active risk flags."""
    flags = LotRiskFlags.objects.filter(lot=lot).first()
    if flags is None:
        return [], []
    critical = [_RISK_LABELS_RU[f] for f in _CRITICAL_RISK_FIELDS if getattr(flags, f, False)]
    warning = [_RISK_LABELS_RU[f] for f in _WARNING_RISK_FIELDS if getattr(flags, f, False)]
    return critical, warning


def compute_verdict(lot: Lot) -> TrafficLightVerdict:
    """Compute and persist the traffic light verdict for a lot."""
    benefit = lot.net_benefit_rub or 0
    percentage = lot.benefit_percentage or 0.0
    critical, warning = collect_risk_factors(lot)
    meti_risk = bool(lot.meti_sanction_risk)

    if critical or meti_risk or benefit < YELLOW_BENEFIT_MIN_RUB:
        color = TrafficLightColor.RED
    elif warning or benefit < GREEN_BENEFIT_MIN_RUB:
        color = TrafficLightColor.YELLOW
    else:
        color = TrafficLightColor.GREEN

    benefit_str = f"{benefit:+,} ₽".replace(",", " ")
    if color == TrafficLightColor.GREEN:
        headline = "🟢 РЕКОМЕНДОВАНО К ПОКУПКЕ"
        badge_text = f"Выгода: {benefit_str}"
    elif color == TrafficLightColor.YELLOW:
        headline = "🟡 ВНИМАНИЕ: ЕСТЬ НЮАНСЫ"
        caveat = ", ".join(warning[:2])
        badge_text = f"Выгода: {benefit_str} ({caveat})" if caveat else f"Выгода: {benefit_str}"
    else:
        headline = "🔴 ПОКУПКУ НЕ РЕКОМЕНДУЕМ"
        reasons = critical + (["санкционный риск экспорта (METI)"] if meti_risk else [])
        if benefit < YELLOW_BENEFIT_MIN_RUB:
            reasons.append("низкая выгода")
        badge_text = "Стоп-факторы: " + ", ".join(reasons[:3])

    body_bits: list[str] = []
    if warning:
        body_bits.append("Кузов: " + ", ".join(warning))
    else:
        body_bits.append("Кузов: без существенных замечаний")
    interior_bits: list[str] = []
    if lot.overall_grade:
        interior_bits.append(f"Оценка аукциона {lot.overall_grade}")
    if lot.odometer_status and lot.odometer_status != OdometerStatus.CONFIRMED:
        interior_bits.append("пробег требует проверки")
    if lot.mileage_km:
        interior_bits.append(f"пробег {lot.mileage_km:,} км".replace(",", " "))

    bullets = [
        f"Чистая выгода: {benefit_str} ({percentage:.1f}%)",
        f"Итого под ключ: {lot.turnkey_cost_rub:,} ₽".replace(",", " ")
        if lot.turnkey_cost_rub
        else "Итого под ключ: не рассчитано",
        f"Рыночная цена РФ: {lot.market_price_rf_rub:,} ₽".replace(",", " ")
        if lot.market_price_rf_rub
        else "Рыночная цена РФ: не определена",
    ]
    bullets += [f"Стоп-фактор: {label}" for label in critical]

    with transaction.atomic():
        verdict_model = TrafficLightVerdict.objects.update_or_create(
            lot=lot,
            defaults={
                "verdict": color,
                "headline": headline,
                "short_verdict_label": headline,
                "badge_text": badge_text,
                "net_benefit_rub": benefit,
                "benefit_percentage": percentage,
                "body_summary_ru": "; ".join(body_bits),
                "interior_summary_ru": "; ".join(interior_bits) or "Данные салона не распознаны",
                "reasoning_bullets": bullets,
            },
        )[0]

    lot.verdict = color
    lot.verdict_headline = headline
    lot.save(update_fields=["verdict", "verdict_headline", "updated_at"])
    return verdict_model
