"""Unit tests for SheetFactory and Markdown passport renderer."""

from ml_service.domains.entities import (
    GatekeeperDecisionEntity,
    RawDefectEntity,
    RawRiskFlagsEntity,
)
from ml_service.domains.enums import (
    BodyPanel,
    FrameIdConfidence,
    LayoutComplexity,
    OdometerStatus,
    ParseStatus,
)
from ml_service.factories.sheet_factory import SheetFactory, _is_repaired_grade
from tests.conftest import make_raw_extraction


def test_sheet_factory_builds_ok_result_and_markdown() -> None:
    factory = SheetFactory(reference_year=2026, reference_month=11, default_auction_strictness=0.65)
    ext = make_raw_extraction()
    gatekeeper = GatekeeperDecisionEntity(
        is_auction_sheet=True,
        is_readable=True,
        complexity=LayoutComplexity.CLEAN_DIGITAL,
        model_used="gemini-decision-1",
        duration_ms=42,
        warning="gatekeeper_unavailable:TimeoutError",
    )
    result = factory.build_result(
        ext,
        processing_ms=350,
        mode_used="clean_digital",
        cached=False,
        model_used="gemini-3.6-flash",
        sha256="abc123",
        gatekeeper=gatekeeper,
    )

    assert result.status == ParseStatus.OK
    assert result.sheet is not None
    assert result.sheet.auction_house == "TAA"
    assert result.sheet.auction_strictness_index == 1.0
    assert result.sheet.frame_id == "ZWE211-6012345"
    assert result.sheet.color_ru == "Белый перламутр"
    assert "gatekeeper_unavailable:TimeoutError" in result.warnings
    assert result.meta.gatekeeper_ms == 42
    assert result.meta.header_ms is None
    assert result.summary_md is not None
    assert "**Аукционный дом:** TAA (индекс строгости: 1.0)" in result.summary_md
    assert "ZWE211-6012345" in result.summary_md


def test_sheet_factory_partial_warnings_and_critical_alerts() -> None:
    factory = SheetFactory(reference_year=2026, reference_month=11, default_auction_strictness=0.65)
    ext = make_raw_extraction(
        auction_house_raw=None,
        auction_house=None,
        first_reg_raw="",
        chassis_number_raw="BAD",
        model_code_raw="",
        make_en="",
        model_en="",
        engine_cc=None,
        mileage_km=None,
        drive_type=None,
        odometer_status=OdometerStatus.TAMPERED,
        overall_grade="RA",
        defects=[
            RawDefectEntity(
                visual_location="левый порог",
                panel_id=BodyPanel.LEFT_SILL,
                panel_ru="Левый порог",
                raw_code="C2/X",
            ),
            RawDefectEntity(
                visual_location="крыша",
                panel_id=BodyPanel.ROOF,
                panel_ru="Крыша",
                raw_code="???",
            ),
        ],
        risk_flags=RawRiskFlagsEntity(
            is_flooded=True,
            airbag_deployed=True,
            hail_damage=True,
            color_changed=True,
        ),
    )

    result = factory.build_result(
        ext,
        processing_ms=100,
        mode_used="complex_or_handwritten",
        cached=False,
        model_used="gemini-3.6-flash",
        sha256="deadbeef",
    )

    assert result.status == ParseStatus.PARTIAL
    assert result.sheet is not None
    assert result.sheet.auction_house is None
    assert "unidentified_auction_house" in result.warnings
    assert "unparsed_registration_date" in result.warnings
    assert "missing_engine_cc" in result.warnings
    assert "missing_mileage_km" in result.warnings
    assert "drive_type_not_marked_on_sheet" in result.warnings
    assert "unknown_defect_code:???" in result.warnings
    assert set(result.low_confidence_fields) >= {
        "first_reg_date_str",
        "chassis_number",
        "model_code",
        "make",
        "model",
        "engine_cc",
        "mileage_km",
    }
    flags = result.sheet.risk_flags
    assert flags.underbody_corrosion is True
    assert flags.panel_needs_replacement_x is True
    assert flags.odometer_issue is True
    assert flags.repaired_grade_r_ra is True
    assert result.summary_md is not None
    assert "КРАСНЫЙ СТОП-ФАКТОР" in result.summary_md
    assert "код X" in result.summary_md


def test_sheet_factory_build_rejected() -> None:
    factory = SheetFactory()
    gatekeeper = GatekeeperDecisionEntity(
        is_auction_sheet=False,
        is_readable=False,
        complexity=LayoutComplexity.COMPLEX_OR_HANDWRITTEN,
        model_used="gemini-decision-1",
        duration_ms=25,
    )
    rejected = factory.build_rejected(
        processing_ms=50,
        sha256="abc",
        model_used="gemini-decision-1",
        gatekeeper=gatekeeper,
    )
    assert rejected.status == ParseStatus.REJECTED_NOT_SHEET
    assert rejected.sheet is None
    assert rejected.warnings == ["image_rejected_by_gatekeeper"]
    assert rejected.meta.gatekeeper_ms == 25


def test_is_repaired_grade_edge_cases() -> None:
    assert _is_repaired_grade("UNRATED") is False
    assert _is_repaired_grade("GRADE 4") is False
    assert _is_repaired_grade("R") is True
    assert _is_repaired_grade("RA") is True
    assert _is_repaired_grade("R1") is True


def test_sheet_factory_auction_house_fallback_and_exact_frame_extra_ru() -> None:
    factory = SheetFactory(reference_year=2026, reference_month=11, default_auction_strictness=0.55)
    ext = make_raw_extraction(
        auction_house_raw="UNKNOWN",
        auction_house="USS",
        chassis_number_raw="ZWE211-6012345",
        extra_ru=["Подогрев сидений"],
    )

    result = factory.build_result(
        ext,
        processing_ms=120,
        mode_used="clean_digital",
        cached=False,
        model_used="gemini-3.6-flash",
        sha256="fedcba",
    )

    assert result.sheet is not None
    assert result.sheet.auction_house == "USS"
    assert result.sheet.auction_strictness_index == 0.75
    assert result.sheet.frame_id_confidence == FrameIdConfidence.EXACT
    assert result.summary_md is not None
    assert "Подогрев сидений" in result.summary_md
