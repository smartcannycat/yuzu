"""Markdown passport renderer for normalized auction sheets."""

from app.domains.entities import NormalizedSheetEntity
from app.domains.enums import FrameIdConfidence, OdometerStatus

_ODOMETER_LABELS: dict[OdometerStatus, str] = {
    OdometerStatus.CONFIRMED: "подтверждён",
    OdometerStatus.REPLACED: "замена одометра (*)",
    OdometerStatus.TAMPERED: "скручен ($)",
    OdometerStatus.UNKNOWN: "неизвестен (#)",
}


def _collect_critical_alerts(sheet: NormalizedSheetEntity) -> list[str]:
    flags = sheet.risk_flags
    alerts: list[str] = []
    if flags.is_flooded:
        alerts.append("КРАСНЫЙ СТОП-ФАКТОР: Автомобиль-топляк / следы затопления (冠水車)")
    if flags.airbag_deployed:
        alerts.append("КРАСНЫЙ СТОП-ФАКТОР: Сработали подушки безопасности (エアバッグ展開)")
    if flags.hail_damage:
        alerts.append("СТОП-ФАКТОР: Автомобиль после сильного града (ひょう害車)")
    if flags.underbody_corrosion:
        alerts.append("КРАСНЫЙ СТОП-ФАКТОР: Сквозная коррозия порогов/днища (腐食/C)")
    if flags.repaired_grade_r_ra:
        alerts.append(f"ВНИМАНИЕ: Аварийный/ремонтный статус лота ({sheet.overall_grade})")
    if flags.panel_needs_replacement_x:
        alerts.append("ВНИМАНИЕ: Детали под обязательную замену (код X) — смета Farpost")
    return alerts


def render_markdown(sheet: NormalizedSheetEntity) -> str:
    """Render a human-readable Russian markdown summary of a normalized auction sheet."""
    lines = ["**Основная информация**"]
    lines.append(f"- **Номер лота:** {sheet.lot_number}")
    if sheet.auction_house:
        strict_str = (
            f" (индекс строгости: {sheet.auction_strictness_index})"
            if sheet.auction_strictness_index is not None
            else ""
        )
        lines.append(f"- **Аукционный дом:** {sheet.auction_house}{strict_str}")
    lines.append(f"- **Марка и модель:** {sheet.make} {sheet.model}")
    if sheet.trim:
        lines.append(f"- **Наименование комплектации:** {sheet.trim}")
    lines.append(f"- **Код кузова (модели):** {sheet.model_code}")
    lines.append(f"- **Номер кузова (шасси):** {sheet.chassis_number}")

    if sheet.frame_id_confidence == FrameIdConfidence.EXACT:
        conf_label = " (верифицирован)"
    elif sheet.frame_id_confidence == FrameIdConfidence.SYNTHESIZED:
        conf_label = " (синтезирован)"
    else:
        conf_label = ""
    lines.append(f"- **Канонический Frame ID:** `{sheet.frame_id}`{conf_label}")

    reg_display = sheet.first_reg_date_str or "[не указано]"
    lines.append(f"- **Дата первой регистрации:** {reg_display}")
    if sheet.color_ru or sheet.paint_code:
        color_parts = ", ".join(p for p in (sheet.color_ru, sheet.paint_code) if p)
        lines.append(f"- **Цвет и заводской код краски:** {color_parts}")
    if sheet.risk_flags.color_changed:
        lines.append("- **Отметка о смене цвета:** да")

    lines.append("\n**Технические характеристики**")
    engine_str = f"{sheet.engine_cc} см³" if sheet.engine_cc else "[не указано]"
    lines.append(f"- **Объем двигателя:** {engine_str}")
    lines.append(f"- **Тип трансмиссии:** {sheet.transmission}")
    if sheet.drive_type:
        lines.append(f"- **Тип привода:** {sheet.drive_type.value}")
    km_str = f"{sheet.mileage_km:,}".replace(",", " ") + " км" if sheet.mileage_km is not None else "[не указано]"
    od_label = _ODOMETER_LABELS.get(sheet.odometer_status, sheet.odometer_status.value)
    lines.append(f"- **Пробег и статус одометра:** {km_str}, {od_label}")
    if sheet.shaken_until:
        lines.append(f"- **Статус техосмотра:** {sheet.shaken_until}")
    if sheet.recycling_fee_yen is not None:
        paid = ", оплачен" if sheet.recycling_fee_paid else ""
        yen_str = f"{sheet.recycling_fee_yen:,}".replace(",", " ")
        lines.append(f"- **Сумма утилизационного сбора:** {yen_str} иен{paid}")

    lines.append("\n**Оценки и оборудование**")
    lines.append(f"- **Общая оценка:** {sheet.overall_grade}")
    if sheet.exterior_grade:
        lines.append(f"- **Оценка кузова:** {sheet.exterior_grade}")
    if sheet.interior_grade:
        lines.append(f"- **Оценка салона:** {sheet.interior_grade}")
    if sheet.equipment_ru:
        lines.append(f"- **Чек-лист базового оборудования:** {', '.join(sheet.equipment_ru)}")

    critical_alerts = _collect_critical_alerts(sheet)
    if critical_alerts:
        lines.append("\n**Предупреждения безопасности и риски:**")
        for alert in critical_alerts:
            lines.append(f"- ⚠️ {alert}")

    lines.append("\n**Состояние и комментарии**")
    defects_str = (
        "; ".join(f"{d.panel_ru}: {d.raw_code}" for d in sheet.defects)
        if sheet.defects
        else "дефекты не отмечены"
    )
    lines.append(f"- **Схема дефектов кузова:** {defects_str}")
    notes_str = "; ".join(sheet.inspector_notes_ru) if sheet.inspector_notes_ru else "[не указано]"
    lines.append(f"- **Замечания инспектора:** {notes_str}")
    if sheet.seller_comments_ru:
        lines.append(f"- **Комментарии продавца:** {'; '.join(sheet.seller_comments_ru)}")

    if sheet.extra_ru:
        lines.append("\n**Дополнительно:**")
        for item in sheet.extra_ru:
            lines.append(f"- {item}")

    return "\n".join(lines)
