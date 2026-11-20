from copy import deepcopy
from datetime import date
from unittest.mock import patch

import pytest
from django.test import Client

from apps.lots.models import Lot
from apps.lots.starter_lots import (
    _load_starter_fixtures,
    _normalize_lot_auction_date,
    _seed_lot_from_fixture,
)


@pytest.mark.django_db
def test_register_seeds_three_starter_lots(api_client: Client) -> None:
    response = api_client.post(
        "/api/v1/auth/register",
        {"email": "new@example.com", "password": "Password123!", "name": "New"},
        content_type="application/json",
    )
    assert response.status_code == 201

    user_id = response.json()["user"]["user_id"]
    lots = list(Lot.objects.filter(user_id=user_id).order_by("created_at"))
    assert len(lots) == 3

    vezel = next(lot for lot in lots if lot.frame_id == "RV3-1005521")
    assert vezel.make == "Honda"
    assert vezel.model == "Vezel"
    assert vezel.lot_number == "55009"
    assert vezel.turnkey_cost_rub == 1818870
    assert vezel.verdict == "yellow"
    assert vezel.completed_at is not None
    assert vezel.sheet_scan.name.endswith(".jpg")
    assert vezel.sheet_thumbnail.name.endswith(".jpg")

    freed = next(lot for lot in lots if lot.frame_id == "GB5-3179736")
    assert freed.make == "Honda"
    assert freed.model == "Freed"
    assert freed.turnkey_cost_rub == 1288182
    assert freed.verdict == "red"
    assert freed.overall_grade == "R"

    accord = next(lot for lot in lots if lot.frame_id == "CV3-1001740")
    assert accord.make == "Honda"
    assert accord.model == "Accord HV"
    assert accord.turnkey_cost_rub == 2536278
    assert accord.verdict == "red"
    assert accord.fuel_type == "hybrid"
    assert accord.meti_sanction_risk is True


@pytest.mark.django_db
def test_freed_starter_lot_has_full_related_data(api_client: Client) -> None:
    response = api_client.post(
        "/api/v1/auth/register",
        {"email": "detail@example.com", "password": "Password123!"},
        content_type="application/json",
    )
    assert response.status_code == 201
    user_id = response.json()["user"]["user_id"]

    freed = Lot.objects.get(user_id=user_id, frame_id="GB5-3179736")

    assert freed.defects.count() == 20
    hood_defect = freed.defects.get(panel_id="hood")
    assert hood_defect.raw_code == "XX"

    assert freed.risk_flags.panel_replaced_xx is True
    assert freed.risk_flags.repaired_grade_r_ra is True

    verdict = freed.verdict_detail
    assert verdict.verdict == "red"
    assert verdict.net_benefit_rub == 231818
    assert len(verdict.reasoning_bullets) >= 2

    market = freed.market_info
    assert market.market_price_rf_rub == 1520000
    assert market.analogs_count == 6

    audit = freed.cross_audit
    assert audit.history.count() >= 0

    checklist = freed.safety_checklist
    assert checklist.items.count() == 5

    customs = freed.customs_calc
    assert customs.age_corridor == "3_to_5_years"
    assert customs.utilization_fee_rub == 5200

    repair = freed.farpost_repair
    assert repair.parts.count() == 4
    assert repair.grand_total_repair_rub == repair.total_parts_from_rub + repair.total_works_rub

    ladder = freed.wise_cost_ladder
    assert ladder.turnkey_cost_rub == 1288182
    assert ladder.steps.count() == 7
    assert sum(step.amount_rub for step in ladder.steps.all()) == ladder.turnkey_cost_rub


@pytest.mark.django_db
def test_starter_lots_are_isolated_per_user(api_client: Client, user_factory) -> None:
    user_factory(email="existing@example.com", password="Password123!")
    assert Lot.objects.filter(user__email="existing@example.com").count() == 0

    response = api_client.post(
        "/api/v1/auth/register",
        {"email": "fresh@example.com", "password": "Password123!"},
        content_type="application/json",
    )
    assert response.status_code == 201

    fresh_lots = Lot.objects.filter(user__email="fresh@example.com")
    assert fresh_lots.count() == 3
    assert not fresh_lots.filter(user__email="existing@example.com").exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("raw_date", "expected"),
    [
        ("2026-11-10", "10.11.2026"),
        (date(2026, 11, 10), "10.11.2026"),
        ("10.11.2026", "10.11.2026"),
        (None, None),
    ],
)
def test_starter_lots_normalizes_lot_auction_date_to_dd_mm_yyyy_string(
    user_factory,
    raw_date: str | date | None,
    expected: str | None,
) -> None:
    from django.utils import timezone

    normalized = _normalize_lot_auction_date(raw_date)
    assert normalized == expected
    if normalized is not None:
        assert isinstance(normalized, str)
        assert not isinstance(normalized, date)

    user = user_factory(email=f"date-{type(raw_date).__name__}@example.com")
    base_fixture = deepcopy(next(iter(_load_starter_fixtures().values())))
    base_fixture["lot_fields"]["auction_date"] = normalized
    with patch("apps.lots.starter_lots.attach_starter_sheet_media"):
        lot = _seed_lot_from_fixture(user, timezone.now(), base_fixture)
    lot.refresh_from_db()
    assert lot.auction_date == expected
    if expected is not None:
        assert isinstance(lot.auction_date, str)
        assert lot.expires_at is not None
