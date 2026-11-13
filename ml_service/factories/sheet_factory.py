"""Factory assembling normalized domain results from raw Vision LLM extractions."""

from app.domains.entities import (
    FastHeaderPreviewEntity,
    GatekeeperDecisionEntity,
    NormalizedDefectEntity,
    NormalizedSheetEntity,
    ParserMetaEntity,
    ParserResultEntity,
    RawDefectEntity,
    RawExtractionEntity,
    RiskFlagsEntity,
)
from app.domains.enums import AuctionHouse, DefectCode, FrameIdConfidence, OdometerStatus, ParseStatus
from app.factories.markdown_renderer import render_markdown
from app.factories.normalizers import (
    CHASSIS_RE,
    KATASHIKI_RE,
    build_defect_description_ru,
    calculate_age_and_corridor,
    clean_code,
    clean_color_ru,
    derive_structural_risk_flags,
    normalize_auction_house,
    normalize_body_panel,
    normalize_transmission_ru,
    parse_defect_codes_with_warnings,
    parse_japanese_date,
    synthesize_frame_id,
)

_REPAIRED_GRADES = {"R", "RA", "0", "★", "***", "99", "1", "2"}


def _normalize_defects(
    raw_defects: list[RawDefectEntity],
) -> tuple[list[NormalizedDefectEntity], bool, bool, bool, list[str]]:
    norm_defects: list[NormalizedDefectEntity] = []
    has_xx = False
    has_x = False
    has_severe_corrosion_c = False
    defect_warnings: list[str] = []

    for defect in raw_defects:
        panel_id, panel_ru = normalize_body_panel(
            defect.panel_id,
            defect.panel_ru,
            defect.visual_location,
        )
        parsed_codes, code_warnings = parse_defect_codes_with_warnings(defect.raw_code)
        defect_warnings.extend(code_warnings)

        for d_type, severity in parsed_codes:
            if d_type == DefectCode.XX:
                has_xx = True
            elif d_type == DefectCode.X:
                has_x = True
            elif d_type == DefectCode.C:
                has_severe_corrosion_c = True

            norm_defects.append(
                NormalizedDefectEntity(
                    panel_id=panel_id,
                    panel_ru=panel_ru,
                    defect_types=[d_type],
                    severity=severity,
                    raw_code=defect.raw_code,
                    description_ru=build_defect_description_ru(panel_ru, d_type, severity),
                )
            )

    return norm_defects, has_xx, has_x, has_severe_corrosion_c, defect_warnings


def _is_repaired_grade(overall_grade: str) -> bool:
    grade_up = overall_grade.strip().upper()
    return grade_up in _REPAIRED_GRADES or grade_up.startswith("R") or "R" in grade_up


class SheetFactory:
    """Assembles canonical ParserResultEntity instances from raw extractions or gatekeeper rejections."""

    def __init__(
        self,
        reference_year: int = 2026,
        reference_month: int = 11,
        default_auction_strictness: float = 0.65,
    ) -> None:
        self._reference_year = reference_year
        self._reference_month = reference_month
        self._default_auction_strictness = default_auction_strictness

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
    ) -> ParserResultEntity:
        """Normalize raw Vision extraction into a complete ParserResultEntity."""
        warnings: list[str] = list(ext.ocr_warnings)
        if gatekeeper and gatekeeper.warning:
            warnings.append(gatekeeper.warning)
        low_conf = list(ext.unreadable_fields)

        reg_y, reg_m, _, reg_ambig = parse_japanese_date(
            ext.first_reg_raw,
            is_future_date=False,
            current_year=self._reference_year,
        )
        if reg_ambig:
            warnings.append("ambiguous_bare_year_without_era")
        if reg_y is None:
            warnings.append("unparsed_registration_date")
            low_conf.append("first_reg_date_str")

        reg_age_str, is_pass_corridor = calculate_age_and_corridor(
            reg_y,
            reg_m,
            reference_year=self._reference_year,
            reference_month=self._reference_month,
        )

        _, _, shaken_str, _ = parse_japanese_date(
            ext.shaken_raw,
            is_future_date=True,
            current_year=self._reference_year,
        )

        chassis = clean_code(ext.chassis_number_raw)
        katashiki = clean_code(ext.model_code_raw)
        paint_code = clean_code(ext.paint_code_raw) or None

        if not CHASSIS_RE.match(chassis.upper()):
            warnings.append("invalid_chassis_format")
            low_conf.append("chassis_number")
        if not KATASHIKI_RE.match(katashiki.upper()):
            warnings.append("invalid_model_code_format")
            low_conf.append("model_code")
        if not ext.make_en.strip():
            low_conf.append("make")
        if not ext.model_en.strip():
            low_conf.append("model")
        if ext.drive_type is None:
            warnings.append("drive_type_not_marked_on_sheet")
        if ext.engine_cc is None:
            warnings.append("missing_engine_cc")
            low_conf.append("engine_cc")
        if ext.mileage_km is None:
            warnings.append("missing_mileage_km")
            low_conf.append("mileage_km")

        auc_house, auc_strict = normalize_auction_house(
            ext.auction_house_raw or ext.auction_house,
            default_strictness=self._default_auction_strictness,
        )
        if auc_house is None:
            warnings.append("unidentified_auction_house")
        elif auc_house == AuctionHouse.OTHER.value:
            warnings.append("auction_house_other")

        frame_id, frame_conf = synthesize_frame_id(katashiki, chassis)
        if frame_conf == FrameIdConfidence.RAW:
            warnings.append("unverified_frame_id_format")

        norm_defects, has_xx, has_x, has_severe_corrosion_c, defect_warnings = _normalize_defects(ext.defects)
        warnings.extend(defect_warnings)

        defect_texts = [f"{d.visual_location} {d.panel_ru} {d.raw_code}" for d in ext.defects]
        pillar_or_frame, core_support = derive_structural_risk_flags(
            llm_pillar_or_frame=ext.risk_flags.pillar_or_frame_repair,
            llm_core_support=ext.risk_flags.core_support_repair,
            inspector_notes_raw=ext.inspector_notes_raw,
            inspector_notes_ru=ext.inspector_notes_ru,
            defect_texts=defect_texts,
        )

        risk_flags = RiskFlagsEntity(
            is_flooded=ext.risk_flags.is_flooded,
            airbag_deployed=ext.risk_flags.airbag_deployed,
            hail_damage=ext.risk_flags.hail_damage,
            underbody_rust=ext.risk_flags.underbody_rust,
            underbody_corrosion=ext.risk_flags.underbody_corrosion or has_severe_corrosion_c,
            core_support_repair=core_support,
            pillar_or_frame_repair=pillar_or_frame,
            panel_replaced_xx=has_xx,
            panel_needs_replacement_x=has_x,
            odometer_issue=(ext.odometer_status != OdometerStatus.CONFIRMED),
            color_changed=ext.risk_flags.color_changed,
            windshield_damage=ext.risk_flags.windshield_damage,
            repaired_grade_r_ra=_is_repaired_grade(ext.overall_grade),
        )

        ocr_warnings = sorted(set(defect_warnings + list(ext.ocr_warnings)))
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
            extra_ru=ext.extra_ru,
            auction_branch=ext.auction_branch,
            right_hand_drive=ext.right_hand_drive,
            name_change_deadline=ext.name_change_deadline,
            inspector_notes_raw=list(ext.inspector_notes_raw),
            ocr_warnings=ocr_warnings,
        )

        summary_md = render_markdown(sheet)
        status = ParseStatus.PARTIAL if low_conf else ParseStatus.OK

        return ParserResultEntity(
            status=status,
            warnings=sorted(set(warnings)),
            low_confidence_fields=sorted(set(low_conf)),
            sheet=sheet,
            raw=ext.to_raw_dict(),
            summary_md=summary_md,
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
