"""Explicit domain-to-API response mappers."""

from uuid import UUID

from ml_service.api.schemas import (
    BatchCreateResponse,
    BatchItemStatusResponse,
    BatchProgressResponse,
    DefectResponse,
    MascotResponse,
    ModelAttemptResponse,
    NormalizedSheetResponse,
    ParserMetaResponse,
    ParserResponse,
    RiskFlagsResponse,
    SheetSummaryProjection,
)
from ml_service.domains.batch_entities import BatchItemStatusEntity, BatchJobEntity
from ml_service.domains.entities import (
    NormalizedDefectEntity,
    NormalizedSheetEntity,
    ParserMetaEntity,
    ParserResultEntity,
    RiskFlagsEntity,
)
from ml_service.domains.enums import BatchStatus


def _to_defect_response(defect: NormalizedDefectEntity) -> DefectResponse:
    return DefectResponse(
        panel_id=defect.panel_id,
        panel_ru=defect.panel_ru,
        defect_types=list(defect.defect_types),
        severity=defect.severity,
        description_ru=defect.description_ru,
        raw_code=defect.raw_code,
    )


def _to_risk_flags_response(flags: RiskFlagsEntity) -> RiskFlagsResponse:
    return RiskFlagsResponse(
        is_flooded=flags.is_flooded,
        airbag_deployed=flags.airbag_deployed,
        hail_damage=flags.hail_damage,
        underbody_rust=flags.underbody_rust,
        underbody_corrosion=flags.underbody_corrosion,
        core_support_repair=flags.core_support_repair,
        pillar_or_frame_repair=flags.pillar_or_frame_repair,
        panel_replaced_xx=flags.panel_replaced_xx,
        panel_needs_replacement_x=flags.panel_needs_replacement_x,
        odometer_issue=flags.odometer_issue,
        color_changed=flags.color_changed,
        windshield_damage=flags.windshield_damage,
        repaired_grade_r_ra=flags.repaired_grade_r_ra,
    )


def _to_sheet_response(sheet: NormalizedSheetEntity) -> NormalizedSheetResponse:
    return NormalizedSheetResponse(
        lot_number=sheet.lot_number,
        auction_house=sheet.auction_house,
        auction_strictness_index=sheet.auction_strictness_index,
        auction_branch=sheet.auction_branch,
        make=sheet.make,
        model=sheet.model,
        trim=sheet.trim,
        model_code=sheet.model_code,
        chassis_number=sheet.chassis_number,
        frame_id=sheet.frame_id,
        frame_id_confidence=sheet.frame_id_confidence,
        first_reg_year=sheet.first_reg_year,
        first_reg_month=sheet.first_reg_month,
        first_reg_date_str=sheet.first_reg_date_str,
        is_pass_corridor_3_5=sheet.is_pass_corridor_3_5,
        engine_cc=sheet.engine_cc,
        mileage_km=sheet.mileage_km,
        odometer_status=sheet.odometer_status,
        transmission=sheet.transmission,
        drive_type=sheet.drive_type,
        fuel_type=sheet.fuel_type,
        right_hand_drive=sheet.right_hand_drive,
        name_change_deadline=sheet.name_change_deadline,
        color_ru=sheet.color_ru,
        paint_code=sheet.paint_code,
        overall_grade=sheet.overall_grade,
        exterior_grade=sheet.exterior_grade,
        interior_grade=sheet.interior_grade,
        shaken_until=sheet.shaken_until,
        recycling_fee_yen=sheet.recycling_fee_yen,
        recycling_fee_paid=sheet.recycling_fee_paid,
        equipment_ru=list(sheet.equipment_ru),
        defects=[_to_defect_response(item) for item in sheet.defects],
        risk_flags=_to_risk_flags_response(sheet.risk_flags),
        inspector_notes_raw=list(sheet.inspector_notes_raw),
        inspector_notes_ru=list(sheet.inspector_notes_ru),
        seller_comments_ru=list(sheet.seller_comments_ru),
        extra_ru=list(sheet.extra_ru),
        ocr_warnings=list(sheet.ocr_warnings),
    )


def _to_meta_response(meta: ParserMetaEntity) -> ParserMetaResponse:
    return ParserMetaResponse(
        processing_ms=meta.processing_ms,
        mode_used=meta.mode_used,
        cached=meta.cached,
        model_used=meta.model_used,
        sha256=meta.sha256,
        gatekeeper_model=meta.gatekeeper_model,
        gatekeeper_ms=meta.gatekeeper_ms,
        header_ms=meta.header_ms,
        extract_ms=meta.extract_ms,
        attempts=[
            ModelAttemptResponse(model=att.model, status=att.status, ms=att.ms)
            for att in meta.attempts
        ],
    )


def to_parser_response(entity: ParserResultEntity) -> ParserResponse:
    """Convert domain ParserResultEntity to external API ParserResponse."""
    return ParserResponse(
        status=entity.status,
        warnings=list(entity.warnings),
        low_confidence_fields=list(entity.low_confidence_fields),
        sheet=_to_sheet_response(entity.sheet) if entity.sheet is not None else None,
        raw=dict(entity.raw) if entity.raw is not None else None,
        summary_md=entity.summary_md,
        meta=_to_meta_response(entity.meta),
    )


def _to_summary_projection(sheet: NormalizedSheetEntity | None) -> SheetSummaryProjection | None:
    if sheet is None:
        return None
    return SheetSummaryProjection(
        lot_number=sheet.lot_number,
        make=sheet.make,
        model=sheet.model,
        year=sheet.first_reg_year,
        engine_cc=sheet.engine_cc,
        model_code=sheet.model_code,
        frame_id=sheet.frame_id,
        overall_grade=sheet.overall_grade,
        auction_house=sheet.auction_house,
        mileage_km=sheet.mileage_km,
        first_reg_date_str=sheet.first_reg_date_str,
        is_pass_corridor_3_5=sheet.is_pass_corridor_3_5,
    )


def _to_batch_item_response(item: BatchItemStatusEntity) -> BatchItemStatusResponse:
    summary = _to_summary_projection(item.result.sheet) if item.result is not None else None
    result_resp = to_parser_response(item.result) if item.result is not None else None
    return BatchItemStatusResponse(
        lot_id=UUID(item.lot_id) if item.lot_id else None,
        file_index=item.file_index,
        original_filename=item.original_filename,
        status=item.status,
        current_step=item.current_step,
        progress_pct=item.progress_pct,
        preview_title=item.preview_title,
        error_message=item.error_message,
        summary=summary,
        result=result_resp,
    )


def _build_mascot(batch: BatchJobEntity) -> MascotResponse:
    if batch.status in {BatchStatus.QUEUED, BatchStatus.PROCESSING}:
        return MascotResponse(
            mood="thinking",
            phrase_ru=f"Распознаем лоты… {batch.processed_count}/{batch.total_items}",
            badge_text=f"{batch.processed_count}/{batch.total_items}",
        )
    if batch.rejected_count > 0:
        return MascotResponse(
            mood="warning",
            phrase_ru="Обнаружены файлы, не являющиеся аукционными листами",
            badge_text=f"Отклонено: {batch.rejected_count}",
        )
    if batch.failed_count > 0:
        return MascotResponse(
            mood="confused",
            phrase_ru=(
                f"Готово {batch.ready_count} из {batch.total_items}, ошибок: {batch.failed_count}"
            ),
            badge_text=f"{batch.ready_count}/{batch.total_items}",
        )
    return MascotResponse(
        mood="happy",
        phrase_ru=f"Все лоты распознаны ({batch.ready_count}/{batch.total_items})",
        badge_text=f"{batch.ready_count}/{batch.total_items}",
    )


def to_batch_create_response(
    batch: BatchJobEntity, poll_interval_ms: int = 1500
) -> BatchCreateResponse:
    """Convert domain BatchJobEntity to compact 202 creation response."""
    return BatchCreateResponse(
        batch_id=UUID(batch.batch_id),
        total_items=batch.total_items,
        status=batch.status,
        created_at=batch.created_at,
        poll_interval_ms=poll_interval_ms,
    )


def to_batch_progress_response(batch: BatchJobEntity) -> BatchProgressResponse:
    """Convert domain BatchJobEntity to detailed polling response."""
    return BatchProgressResponse(
        batch_id=UUID(batch.batch_id),
        created_at=batch.created_at,
        status=batch.status,
        total_count=batch.total_items,
        processed_count=batch.processed_count,
        ready_count=batch.ready_count,
        failed_count=batch.failed_count,
        mascot=_build_mascot(batch),
        items=[_to_batch_item_response(item) for item in batch.items],
    )
