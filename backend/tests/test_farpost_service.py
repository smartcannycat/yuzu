"""Repair calculation, cache provenance and atomic pipeline persistence."""

from dataclasses import replace
from unittest.mock import Mock

import pytest

from apps.core.enums import FuelType, WorkType
from apps.lots.integrations.farpost.client import FarpostFetchError, PartCriteria, PartOffer
from apps.lots.integrations.farpost.service import (
    estimate_repair,
)
from apps.lots.models import Lot, LotDefect

CRITERIA = PartCriteria(
    "Toyota", "Corolla", "NRE210", "front_left_door", "дверь", "левая", "передняя", "070"
)
OFFER = PartOffer(
    "123", "https://www.farpost.ru/vladivostok/zapchasti/door-123.html", "Дверь", 18000, True
)


@pytest.fixture
def lot(user_factory):
    return Lot.objects.create(
        user=user_factory(),
        make="Toyota",
        model="Corolla",
        model_code="NRE210",
        paint_code="070",
        fuel_type=FuelType.GASOLINE,
    )


def defect(lot, code, panel="front_left_door"):
    return LotDefect.objects.create(
        lot=lot, panel_id=panel, panel_ru=panel, raw_code=code, defect_types=[], description_ru=""
    )


def source(offers=None, *, error=False):
    client = Mock()
    client.search.side_effect = FarpostFetchError("unavailable") if error else None
    client.search.return_value = offers if offers is not None else [OFFER]
    return client


@pytest.mark.django_db
@pytest.mark.parametrize("code", ["X", "XX"])
def test_color_match_adds_part_and_mount_but_no_paint(lot, code):
    defect(lot, code)
    result = estimate_repair(lot, client=source())
    assert result.total_parts_from_rub == 18000
    assert result.total_works_rub == 2500
    assert result.grand_total_repair_rub == 20500
    assert result.has_color_matched_parts
    (paint,) = [work for work in result.service_works if work.work_type == WorkType.PAINT]
    assert paint.amount_rub == 0 and paint.zero_cost_reason_ru == "не требуется"
    assert result.parts[0].in_stock_vladivostok
    assert not result.parts[0].is_statistical_fallback


@pytest.mark.django_db
def test_other_color_is_searched_only_after_exact_color_fails(lot):
    defect(lot, "X")
    client = source()
    client.search.side_effect = [[], [replace(OFFER, color_matched=False, price_rub=15000)]]
    result = estimate_repair(lot, client=client)
    assert [c.args[0].paint_code for c in client.search.call_args_list] == ["070", ""]
    assert result.total_parts_from_rub == 15000
    assert result.total_works_rub == 12500
    assert not result.has_color_matched_parts


@pytest.mark.django_db
def test_unknown_color_still_pays_for_paint(lot):
    lot.paint_code = None
    defect(lot, "X")
    client = source([replace(OFFER, color_matched=False)])
    result = estimate_repair(lot, client=client)
    assert client.search.call_args.args[0].paint_code == ""
    assert result.total_works_rub == 12500


@pytest.mark.django_db
@pytest.mark.parametrize("error", [False, True])
def test_empty_or_failed_source_uses_marked_statistics(lot, error):
    defect(lot, "XX")
    result = estimate_repair(lot, client=source([], error=error))
    assert result.grand_total_repair_rub == 41500
    assert result.parts[0].is_statistical_fallback
    assert not result.parts[0].in_stock_vladivostok
    assert not result.has_color_matched_parts


@pytest.mark.django_db
def test_duplicate_and_composite_defects_do_not_duplicate_replacement(lot):
    defect(lot, "X/A2/U2")
    defect(lot, "XX")
    result = estimate_repair(lot, client=source())
    assert len(result.parts) == 1
    assert len(result.service_works) == 2
    assert result.grand_total_repair_rub == 20500


@pytest.mark.django_db
@pytest.mark.parametrize(
    "code,expected", [("A1", 2000), ("AU3", 15000), ("W1", 0), ("U", 15000), ("ZZ9", 21500)]
)
def test_matrix_repairs_need_no_parts_search(lot, code, expected):
    defect(lot, code)
    client = source()
    result = estimate_repair(lot, client=client)
    client.search.assert_not_called()
    assert not result.parts
    assert result.grand_total_repair_rub == expected


@pytest.mark.django_db
def test_fixed_panel_and_glass_rules(lot):
    defect(lot, "X", "roof")
    defect(lot, "X", "windshield")
    result = estimate_repair(lot, client=source([]))
    assert len(result.parts) == 1
    assert result.parts[0].panel_id == "windshield"
    assert {w.work_type for w in result.service_works} == {
        WorkType.BODYWORK,
        WorkType.MOUNT_DISMOUNT,
    }


@pytest.mark.django_db
def test_no_defects_and_missing_identity_do_not_query(lot):
    client = source()
    assert estimate_repair(lot, client=client).grand_total_repair_rub == 0
    lot.model_code = None
    defect(lot, "X")
    assert estimate_repair(lot, client=client).parts[0].is_statistical_fallback
    client.search.assert_not_called()
