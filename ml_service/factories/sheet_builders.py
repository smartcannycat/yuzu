"""Helper functions for defect normalization, risk flags, and auction house resolution."""

import re

from ml_service.domains.entities import (
    NormalizedDefectEntity,
    RawDefectEntity,
    RawExtractionEntity,
    RiskFlagsEntity,
)
from ml_service.domains.enums import AuctionHouse, DefectCode, OdometerStatus
from ml_service.factories.normalizers import (
    CHASSIS_RE,
    KATASHIKI_RE,
    build_defect_description_ru,
    derive_structural_risk_flags,
    normalize_auction_house,
    normalize_body_panel,
    parse_defect_codes_with_warnings,
)

_REPAIRED_GRADE_RE = re.compile(r"^(?:R|RA|RB|RC|R\d|[*\u2605]+|0|1|2|99)$")


def normalize_defects(
    raw_defects: list[RawDefectEntity],
) -> tuple[list[NormalizedDefectEntity], bool, bool, bool, list[str]]:
    """Normalize body diagram defects and collect summary flags and warnings."""
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

        if not parsed_codes:
            raw_label = defect.raw_code.strip() or "не указан"
            norm_defects.append(
                NormalizedDefectEntity(
                    panel_id=panel_id,
                    panel_ru=panel_ru,
                    defect_types=[],
                    severity=None,
                    raw_code=defect.raw_code,
                    description_ru=f"{panel_ru} — код дефекта ({raw_label})",
                )
            )
            continue

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
                    description_ru=build_defect_description_ru(
                        panel_ru,
                        d_type,
                        severity,
                        raw_code=defect.raw_code,
                    ),
                )
            )

    return norm_defects, has_xx, has_x, has_severe_corrosion_c, defect_warnings


def is_repaired_grade(overall_grade: str) -> bool:
    """Return True when the overall auction grade denotes repaired/accident history."""
    grade_up = overall_grade.strip().upper()
    if not grade_up:
        return False
    return bool(_REPAIRED_GRADE_RE.match(grade_up)) or any(
        _REPAIRED_GRADE_RE.match(tok) for tok in re.split(r"[\s/,+]+", grade_up) if tok
    )


def resolve_auction_house(
    ext: RawExtractionEntity,
    *,
    default_strictness: float,
    warnings: list[str],
) -> tuple[str | None, float | None]:
    """Normalize auction house with fallback to translated auction_house field."""
    auc_house, auc_strict = normalize_auction_house(
        ext.auction_house_raw,
        default_strictness=default_strictness,
    )
    if (auc_house is None or auc_house == AuctionHouse.OTHER.value) and ext.auction_house:
        fallback_house, fallback_strict = normalize_auction_house(
            ext.auction_house,
            default_strictness=default_strictness,
        )
        if fallback_house is not None and (
            auc_house is None or fallback_house != AuctionHouse.OTHER.value
        ):
            auc_house, auc_strict = fallback_house, fallback_strict
    if auc_house is None:
        warnings.append("unidentified_auction_house")
    elif auc_house == AuctionHouse.OTHER.value:
        warnings.append("auction_house_other")
    return auc_house, auc_strict


def collect_field_warnings(
    ext: RawExtractionEntity,
    *,
    chassis: str,
    katashiki: str,
    warnings: list[str],
    low_conf: list[str],
) -> None:
    """Append validation warnings and low-confidence field markers."""
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


def build_risk_flags(
    ext: RawExtractionEntity,
    *,
    has_xx: bool,
    has_x: bool,
    has_severe_corrosion_c: bool,
) -> RiskFlagsEntity:
    """Construct complete 13-field RiskFlagsEntity combining LLM and deterministic checks."""
    defect_texts = [f"{d.visual_location} {d.panel_ru} {d.raw_code}" for d in ext.defects]
    pillar_or_frame, core_support = derive_structural_risk_flags(
        llm_pillar_or_frame=ext.risk_flags.pillar_or_frame_repair,
        llm_core_support=ext.risk_flags.core_support_repair,
        inspector_notes_raw=ext.inspector_notes_raw,
        inspector_notes_ru=ext.inspector_notes_ru,
        defect_texts=defect_texts,
    )
    return RiskFlagsEntity(
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
        repaired_grade_r_ra=is_repaired_grade(ext.overall_grade),
    )
