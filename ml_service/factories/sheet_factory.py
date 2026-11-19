"""Factory assembling normalized domain results from raw Vision LLM extractions."""

from ml_service.config import resolve_reference_date
from ml_service.domains.entities import (
    FastHeaderPreviewEntity,
    GatekeeperDecisionEntity,
    NormalizedSheetEntity,
    ParserMetaEntity,
    ParserResultEntity,
    RawExtractionEntity,
)
from ml_service.domains.enums import FrameIdConfidence, ParseStatus
from ml_service.factories.markdown_renderer import render_markdown
from ml_service.factories.normalizers import (
    calculate_age_and_corridor,
    clean_code,
    clean_color_ru,
    normalize_transmission_ru,
    parse_japanese_date,
    synthesize_frame_id,
)
from ml_service.factories.sheet_builders import (
    build_risk_flags,
    collect_field_warnings,
    normalize_defects,
    resolve_auction_house,
)
from ml_service.factories.sheet_builders import (
    is_repaired_grade as _is_repaired_grade,
)

__all__ = ["SheetFactory", "_is_repaired_grade"]


class SheetFactory:
    """Assembles canonical ParserResultEntity instances from extractions or rejections."""

    def __init__(
        self,
        reference_year: int | None = None,
        reference_month: int | None = None,
        default_auction_strictness: float = 0.65,
    ) -> None:
        self._reference_year = reference_year
        self._reference_month = reference_month
        self._default_auction_strictness = default_auction_strictness

    @property
    def default_auction_strictness(self) -> float:
        return self._default_auction_strictness

    def resolve_reference_date(self) -> tuple[int, int]:
        """Return effective (year, month), defaulting omitted fields to current JST date."""
        return resolve_reference_date(self._reference_year, self._reference_month)

    def build_result(
        self,
        ext: RawExtractionEntity,
        *,
        processing_ms: int,
        mode_used: str,
        cached: bool,
        model_used: str,
        sha256: str,
        gatekeeper: GatekeeperDecisionEntity | None = None,
        header_preview: FastHeaderPreviewEntity | None = None,
        reference_date: tuple[int, int] | None = None,
    ) -> ParserResultEntity:
        """Normalize raw Vision extraction into a complete ParserResultEntity."""
        ref_year, ref_month = reference_date or self.resolve_reference_date()
        warnings: list[str] = list(ext.ocr_warnings)
        if gatekeeper and gatekeeper.warning:
            warnings.append(gatekeeper.warning)
        low_conf = list(ext.unreadable_fields)

        reg_y, reg_m, _, reg_ambig = parse_japanese_date(
            ext.first_reg_raw, is_future_date=False, current_year=ref_year
        )
        if reg_ambig:
            warnings.append("ambiguous_bare_year_without_era")
        if reg_y is None:
            warnings.append("unparsed_registration_date")
            low_conf.append("first_reg_date_str")

        reg_age_str, is_pass_corridor = calculate_age_and_corridor(
            reg_y, reg_m, reference_year=ref_year, reference_month=ref_month
        )
        _, _, shaken_str, _ = parse_japanese_date(
            ext.shaken_raw, is_future_date=True, current_year=ref_year
        )

        chassis = clean_code(ext.chassis_number_raw)
        katashiki = clean_code(ext.model_code_raw)
        paint_code = clean_code(ext.paint_code_raw) or None
        collect_field_warnings(
            ext, chassis=chassis, katashiki=katashiki, warnings=warnings, low_conf=low_conf
        )

        auc_house, auc_strict = resolve_auction_house(
            ext, default_strictness=self._default_auction_strictness, warnings=warnings
        )
        frame_id, frame_conf = synthesize_frame_id(katashiki, chassis)
        if frame_conf == FrameIdConfidence.RAW:
            warnings.append("unverified_frame_id_format")

        norm_defects, has_xx, has_x, has_corr_c, defect_warnings = normalize_defects(ext.defects)
        warnings.extend(defect_warnings)
        risk_flags = build_risk_flags(
            ext, has_xx=has_xx, has_x=has_x, has_severe_corrosion_c=has_corr_c
        )

        extra_ru = list(ext.extra_ru)
        if ext.color_changed_ru and ext.color_changed_ru not in extra_ru:
            extra_ru.append(ext.color_changed_ru)

        sheet = NormalizedSheetEntity(
            lot_number=clean_code(ext.lot_number_raw),
            auction_house=auc_house,
            auction_strictness_index=auc_strict,
            make=ext.make_en,
            model=ext.model_en,
            trim=ext.trim_en,
            model_code=katashiki,
            chassis_number=chassis,
            frame_id=frame_id,
            frame_id_confidence=frame_conf,
            first_reg_year=reg_y,
            first_reg_month=reg_m,
            first_reg_date_str=reg_age_str,
            is_pass_corridor_3_5=is_pass_corridor,
            engine_cc=ext.engine_cc,
            mileage_km=ext.mileage_km,
            odometer_status=ext.odometer_status,
            transmission=normalize_transmission_ru(ext.transmission_raw, ext.transmission_ru),
            drive_type=ext.drive_type,
            fuel_type=ext.fuel_type,
            color_ru=clean_color_ru(ext.color_ru, paint_code),
            paint_code=paint_code,
            overall_grade=ext.overall_grade,
            exterior_grade=ext.exterior_grade,
            interior_grade=ext.interior_grade,
            shaken_until=shaken_str or ext.shaken_ru,
            recycling_fee_yen=ext.recycling_fee_yen,
            recycling_fee_paid=ext.recycling_fee_paid,
            equipment_ru=ext.equipment_ru,
            defects=norm_defects,
            risk_flags=risk_flags,
            inspector_notes_ru=ext.inspector_notes_ru,
            seller_comments_ru=ext.seller_comments_ru,
            extra_ru=extra_ru,
            auction_branch=ext.auction_branch,
            right_hand_drive=ext.right_hand_drive,
            name_change_deadline=ext.name_change_deadline,
            inspector_notes_raw=list(ext.inspector_notes_raw),
            ocr_warnings=sorted(set(defect_warnings + list(ext.ocr_warnings))),
        )
        return ParserResultEntity(
            status=ParseStatus.PARTIAL if low_conf else ParseStatus.OK,
            warnings=sorted(set(warnings)),
            low_confidence_fields=sorted(set(low_conf)),
            sheet=sheet,
            raw=ext.to_raw_dict(),
            summary_md=render_markdown(sheet),
            meta=ParserMetaEntity(
                processing_ms=processing_ms,
                mode_used=mode_used,
                cached=cached,
                model_used=model_used,
                sha256=sha256,
                gatekeeper_model=gatekeeper.model_used if gatekeeper else None,
                gatekeeper_ms=gatekeeper.duration_ms if gatekeeper else 0,
                header_ms=header_preview.duration_ms if header_preview else None,
                extract_ms=ext.extract_ms,
                attempts=list(ext.attempts),
            ),
        )

    def build_rejected(
        self,
        *,
        processing_ms: int,
        sha256: str,
        model_used: str,
        reason: str = "image_rejected_by_gatekeeper",
        gatekeeper: GatekeeperDecisionEntity | None = None,
    ) -> ParserResultEntity:
        """Build a rejected result when the input image is not a readable auction sheet."""
        return ParserResultEntity(
            status=ParseStatus.REJECTED_NOT_SHEET,
            warnings=[reason] if reason else [],
            low_confidence_fields=[],
            sheet=None,
            raw=None,
            summary_md=None,
            meta=ParserMetaEntity(
                processing_ms=processing_ms,
                mode_used="gatekeeper",
                cached=False,
                model_used=model_used,
                sha256=sha256,
                gatekeeper_model=gatekeeper.model_used if gatekeeper else model_used,
                gatekeeper_ms=gatekeeper.duration_ms if gatekeeper else processing_ms,
            ),
        )
