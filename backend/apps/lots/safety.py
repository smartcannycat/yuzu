"""Safety checklist and cross-audit baseline derived from parsed sheet data.

The external auction-history archive (AucJP / AAA Japan, BE-08) is not
integrated yet, so the cross-audit step records an honest ``not_found``
baseline instead of silently passing. The safety checklist derives the
five canonical systems from the sheet's risk flags and inspector notes.
"""

import logging

from django.db import transaction
from django.utils import timezone

from apps.core.enums import (
    ChecklistItemStatus,
    CrossAuditStatus,
    RiskLevel,
    SystemKey,
)
from apps.lots.models import CrossAuditReport, Lot, LotRiskFlags, SafetyCheckItem, SafetyChecklist

logger = logging.getLogger(__name__)


def build_safety_checklist(lot: Lot) -> SafetyChecklist:
    """Derive the five-system safety checklist from sheet risk flags."""
    flags = LotRiskFlags.objects.filter(lot=lot).first()
    if flags is None:
        flags = LotRiskFlags.objects.create(lot=lot)

    has_critical = any(
        (flags.is_flooded, flags.airbag_deployed, flags.underbody_corrosion),
    )

    items: list[dict[str, object]] = [
        {
            "system_key": SystemKey.STRUCTURAL_FRAME,
            "label_ru": "Силовой каркас и лонжероны",
            "status": (
                ChecklistItemStatus.CRITICAL
                if flags.pillar_or_frame_repair
                else ChecklistItemStatus.WARNING
                if flags.core_support_repair
                else ChecklistItemStatus.OK
            ),
            "detail_ru": (
                "Отмечен ремонт стоек или лонжеронов (ピラー/フレーム)"
                if flags.pillar_or_frame_repair
                else "Отмечен ремонт рамки радиатора (コアサポート)"
                if flags.core_support_repair
                else "Нарушений геометрии и ремонта несущих элементов не отмечено"
            ),
        },
        {
            "system_key": SystemKey.AIRBAGS_SRS,
            "label_ru": "Подушки безопасности (SRS)",
            "status": (
                ChecklistItemStatus.CRITICAL if flags.airbag_deployed else ChecklistItemStatus.OK
            ),
            "detail_ru": (
                "Отмечено срабатывание подушек безопасности (エアバッグ展開)"
                if flags.airbag_deployed
                else "Отметок о срабатывании или отсутствии подушек нет"
            ),
        },
        {
            "system_key": SystemKey.ENGINE_TRANSMISSION,
            "label_ru": "ДВС и трансмиссия",
            "status": (
                ChecklistItemStatus.WARNING
                if lot.odometer_status and lot.odometer_status != "confirmed"
                else ChecklistItemStatus.OK
            ),
            "detail_ru": (
                "Проблемы с одометром: скручен, заменён или неизвестен"
                if lot.odometer_status and lot.odometer_status != "confirmed"
                else "Замечаний инспектора по работе двигателя и КПП нет"
            ),
        },
        {
            "system_key": SystemKey.UNDERBODY_CORROSION,
            "label_ru": "Днище и пороги",
            "status": (
                ChecklistItemStatus.CRITICAL
                if flags.underbody_corrosion
                else ChecklistItemStatus.WARNING
                if flags.underbody_rust
                else ChecklistItemStatus.OK
            ),
            "detail_ru": (
                "Сквозная коррозия днища и порогов (腐食/C)"
                if flags.underbody_corrosion
                else "Поверхностная ржавчина днища (下廻り S)"
                if flags.underbody_rust
                else "Сквозная коррозия не отмечена"
            ),
        },
        {
            "system_key": SystemKey.FLOOD_OR_FIRE,
            "label_ru": "Следы затопления / пожара / града",
            "status": (
                ChecklistItemStatus.CRITICAL
                if has_critical
                else ChecklistItemStatus.WARNING
                if flags.hail_damage
                else ChecklistItemStatus.OK
            ),
            "detail_ru": (
                "Стоп-факторы в бланке зафиксированы: затопление или сквозная коррозия"
                if flags.is_flooded or flags.underbody_corrosion
                else "Отмечен градобой (ひょう害車)"
                if flags.hail_damage
                else "Стоп-факторов в бланке не зафиксировано"
            ),
        },
    ]

    statuses = [item["status"] for item in items]
    if ChecklistItemStatus.CRITICAL in statuses:
        overall = ChecklistItemStatus.CRITICAL
        label = "Есть критические замечания"
    elif ChecklistItemStatus.WARNING in statuses:
        overall = ChecklistItemStatus.WARNING
        label = "Есть нюансы"
    else:
        overall = ChecklistItemStatus.OK
        label = "В норме"

    with transaction.atomic():
        checklist = SafetyChecklist.objects.update_or_create(
            lot=lot,
            defaults={"overall_status": overall, "overall_label_ru": label},
        )[0]
        SafetyCheckItem.objects.filter(checklist=checklist).delete()
        SafetyCheckItem.objects.bulk_create(
            SafetyCheckItem(checklist=checklist, **item) for item in items
        )
    return checklist


def build_cross_audit_baseline(lot: Lot) -> CrossAuditReport:
    """Record the honest cross-audit baseline for a freshly parsed lot.

    The archive gateways (AucJP / AAA Japan / Pravto) are not integrated
    yet; until BE-08 lands, every lot gets ``not_found`` with zero history
    rather than a fabricated clean bill. Sheet-internal red flags still
    drive ``has_critical_anomaly`` so sticky alerts do not regress.
    """
    flags = LotRiskFlags.objects.filter(lot=lot).first()
    critical_flags = bool(
        flags
        and (
            flags.is_flooded
            or flags.airbag_deployed
            or flags.underbody_corrosion
            or flags.odometer_issue
            or flags.repaired_grade_r_ra
        )
    )
    has_anomaly = critical_flags
    if has_anomaly:
        headline = (
            "Критические отметки на листе (стоп-факторы безопасности); "
            "внешние архивы торгов пока не проверены"
        )
        risk = RiskLevel.CRITICAL
        status = CrossAuditStatus.ANOMALY_DETECTED
    else:
        headline = (
            "Критических отметок на листе нет; внешние архивы торгов "
            "(AucJP / AAA Japan) пока не проверены"
        )
        risk = RiskLevel.INFO
        status = CrossAuditStatus.NOT_FOUND

    report = CrossAuditReport.objects.update_or_create(
        lot=lot,
        defaults={
            "status": status,
            "is_archive_available": False,
            "risk_level": risk,
            "has_critical_anomaly": has_anomaly,
            "headline_ru": headline,
            "times_auctioned": 0,
            "verified_at": timezone.now(),
        },
    )[0]

    lot.has_anomaly = has_anomaly
    lot.anomaly_text = headline[:500] if has_anomaly else None
    lot.save(update_fields=["has_anomaly", "anomaly_text", "updated_at"])
    return report
