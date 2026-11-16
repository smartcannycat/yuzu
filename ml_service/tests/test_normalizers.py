"""Unit tests for deterministic normalizers in factories/normalizers.py."""

import pytest

from ml_service.domains.enums import AuctionHouse, BodyPanel, DefectCode, FrameIdConfidence
from ml_service.factories.normalizers import (
    AUCTION_STRICTNESS,
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
    split_defect_codes,
    synthesize_frame_id,
)


def test_clean_code_normalizes_fullwidth_and_spaces() -> None:
    assert clean_code("　ＮＲＥ２１０ － ２００５４１８ ") == "NRE210-2005418"
    assert clean_code(None) == ""


@pytest.mark.parametrize(
    ("raw", "expected_house", "expected_strict"),
    [
        ("TAA 横浜", AuctionHouse.TAA.value, AUCTION_STRICTNESS[AuctionHouse.TAA]),
        ("トヨタオートオークション", AuctionHouse.TAA.value, AUCTION_STRICTNESS[AuctionHouse.TAA]),
        ("Honda Auto Auction", AuctionHouse.HONDA.value, AUCTION_STRICTNESS[AuctionHouse.HONDA]),
        ("HAA神戸", AuctionHouse.HONDA.value, AUCTION_STRICTNESS[AuctionHouse.HONDA]),
        ("USS Tokyo", AuctionHouse.USS.value, AUCTION_STRICTNESS[AuctionHouse.USS]),
        ("ユーエスエス東京", AuctionHouse.USS.value, AUCTION_STRICTNESS[AuctionHouse.USS]),
        ("MIRIVE Saitama", AuctionHouse.MIRIVE.value, AUCTION_STRICTNESS[AuctionHouse.MIRIVE]),
        ("Unknown Regional House", AuctionHouse.OTHER.value, 0.55),
        (None, None, None),
        ("   ", None, None),
        ("UNKNOWN", None, None),
        ("n/a", None, None),
    ],
)
def test_normalize_auction_house(
    raw: str | None,
    expected_house: str | None,
    expected_strict: float | None,
) -> None:
    house, strict = normalize_auction_house(raw, default_strictness=0.55)
    assert house == expected_house
    assert strict == expected_strict


def test_normalize_auction_house_avoids_substring_traps() -> None:
    house, _ = normalize_auction_house("RUSSIAN AUTO", default_strictness=0.65)
    assert house == AuctionHouse.OTHER.value


def test_synthesize_frame_id() -> None:
    assert synthesize_frame_id("6AA-ZWE211W", "NRE210-2005418") == (
        "NRE210-2005418",
        FrameIdConfidence.EXACT,
    )
    assert synthesize_frame_id("6AA-RV5", "1356915") == (
        "RV5-1356915",
        FrameIdConfidence.SYNTHESIZED,
    )
    assert synthesize_frame_id("DBA-NRE210W", "2005418") == (
        "NRE210-2005418",
        FrameIdConfidence.SYNTHESIZED,
    )
    assert synthesize_frame_id("", "ABCXYZ") == ("ABCXYZ", FrameIdConfidence.RAW)


def test_parse_defect_codes_and_descriptions() -> None:
    parsed, warnings = parse_defect_codes_with_warnings("A1 / U2 / S小 / XX / Z9")
    assert parsed == [
        (DefectCode.A, 1),
        (DefectCode.U, 2),
        (DefectCode.S, 1),
        (DefectCode.XX, None),
    ]
    assert warnings == ["unknown_defect_code:Z9"]
    assert split_defect_codes("C(小) R X") == [("C", 1), ("R", None), ("X", None)]

    desc_small = build_defect_description_ru("Порог левый", DefectCode.S, 1, raw_code="S小")
    assert desc_small == "Порог левый — ржавчина, степень 1 (small)"
    desc_plain = build_defect_description_ru("", DefectCode.XX, None)
    assert desc_plain == "Кузов — замена детали"


@pytest.mark.parametrize(
    ("raw", "is_future", "expected"),
    [
        ("R4.05", False, (2022, 5, "05.2022", False)),
        ("令和元年11月", False, (2019, 11, "11.2019", False)),
        ("平成三十年3月", False, (2018, 3, "03.2018", False)),
        ("昭和60年", False, (1985, None, "1985", False)),
        ("07.2021", False, (2021, 7, "07.2021", False)),
        ("2022年10月", False, (2022, 10, "10.2022", False)),
        ("4/5", False, (2022, 5, "05.2022", True)),
        ("31.02", False, (2019, 2, "02.2019", False)),
        ("8.05", True, (2026, 5, "05.2026", False)),
        ("H30 (2018) 5月", False, (2018, 5, "05.2018", False)),
        ("R4年 1000km", False, (2022, None, "2022", False)),
        ("令和元.05", False, (2019, 5, "05.2019", False)),
        ("unparseable", False, (None, None, "unparseable", True)),
        (None, False, (None, None, None, False)),
    ],
)
def test_parse_japanese_date(
    raw: str | None,
    is_future: bool,
    expected: tuple[int | None, int | None, str | None, bool],
) -> None:
    assert parse_japanese_date(raw, is_future_date=is_future, current_year=2026) == expected


def test_calculate_age_and_corridor() -> None:
    assert calculate_age_and_corridor(None, None) == (None, False)

    age_str, in_corridor = calculate_age_and_corridor(
        2022, 5, reference_year=2026, reference_month=11
    )
    assert age_str == "05.2022 (Возраст 4 года 6 мес.)"
    assert in_corridor is True

    age_one, in_corridor_one = calculate_age_and_corridor(
        2025, 11, reference_year=2026, reference_month=11
    )
    assert age_one == "11.2025 (Возраст 1 год 0 мес.)"
    assert in_corridor_one is False

    age_eleven, _ = calculate_age_and_corridor(2015, None, reference_year=2026, reference_month=7)
    assert age_eleven == "2015 (Возраст 11 лет 0 мес.)"

    # Exact 36-to-60-month corridor boundaries (reference 2026-11)
    assert calculate_age_and_corridor(2023, 12, reference_year=2026, reference_month=11)[1] is False
    assert calculate_age_and_corridor(2023, 11, reference_year=2026, reference_month=11)[1] is True
    assert calculate_age_and_corridor(2021, 11, reference_year=2026, reference_month=11)[1] is True
    assert calculate_age_and_corridor(2021, 10, reference_year=2026, reference_month=11)[1] is False


def test_normalize_body_panel_transmission_and_color() -> None:
    assert normalize_body_panel(BodyPanel.FRONT_BUMPER, "", "コアサポート") == (
        BodyPanel.OTHER,
        "Рамка радиатора (Core Support)",
    )
    assert normalize_body_panel(BodyPanel.OTHER, "", "右Fドア") == (
        BodyPanel.FRONT_RIGHT_DOOR,
        "Передняя правая дверь",
    )
    assert normalize_body_panel(BodyPanel.ROOF, "Крыша", "") == (BodyPanel.ROOF, "Крыша")

    assert normalize_transmission_ru("IAT", "") == "вариатор (CVT)"
    assert normalize_transmission_ru("DCT", "") == "робот"
    assert normalize_transmission_ru("6MT", "") == "МКПП"
    assert normalize_transmission_ru("FAT", "") == "АКПП"
    assert normalize_transmission_ru("", "") == "не указано"

    assert clean_color_ru("Белый (070)", "070") == "Белый"
    assert clean_color_ru("Серебро [1F7]", None) == "Серебро [1F7]"
    assert clean_color_ru("Черный (202)", None) == "Черный"
    assert clean_color_ru(None, None) is None


def test_derive_structural_risk_flags() -> None:
    pillar, core = derive_structural_risk_flags(
        llm_pillar_or_frame=True,
        llm_core_support=False,
        inspector_notes_raw=["右インパネ小歪"],
        inspector_notes_ru=[],
        defect_texts=[],
    )
    assert pillar is False
    assert core is False

    pillar2, core2 = derive_structural_risk_flags(
        llm_pillar_or_frame=False,
        llm_core_support=False,
        inspector_notes_raw=["ピラー修理跡", "コアサポート交換"],
        inspector_notes_ru=[],
        defect_texts=[],
    )
    assert pillar2 is True
    assert core2 is True

    pillar3, core3 = derive_structural_risk_flags(
        llm_pillar_or_frame=True,
        llm_core_support=True,
        inspector_notes_raw=["ピラー異常なし", "コアサポート問題なし"],
        inspector_notes_ru=[],
        defect_texts=[],
    )
    assert pillar3 is False
    assert core3 is False

    # Mixed clause: clean pillar clause followed by side-member distortion
    pillar4, core4 = derive_structural_risk_flags(
        llm_pillar_or_frame=False,
        llm_core_support=False,
        inspector_notes_raw=["ピラー異常なし、サイドメンバー歪み"],
        inspector_notes_ru=[],
        defect_texts=[],
    )
    assert pillar4 is True
    assert core4 is False

    # Standalone engine-clean phrase does not suppress unrelated LLM structural flag
    pillar5, core5 = derive_structural_risk_flags(
        llm_pillar_or_frame=True,
        llm_core_support=False,
        inspector_notes_raw=["エンジン異常なし"],
        inspector_notes_ru=[],
        defect_texts=[],
    )
    assert pillar5 is True
    assert core5 is False
