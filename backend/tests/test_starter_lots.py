import pytest
from django.test import Client

from apps.lots.models import Lot


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

    corolla = next(lot for lot in lots if lot.make == "Toyota")
    assert corolla.model == "Corolla Touring"
    assert corolla.frame_id == "NRE210-2005418"
    assert corolla.lot_number == "3142"
    assert corolla.turnkey_cost_rub == 1104899
    assert corolla.verdict == "green"
    assert corolla.completed_at is not None

    vezel = next(lot for lot in lots if lot.make == "Honda")
    assert vezel.model == "Vezel"
    assert vezel.frame_id == "RU3-1209412"
    assert vezel.turnkey_cost_rub == 1480000
    assert vezel.verdict == "yellow"
    assert vezel.fuel_type == "hybrid"
    assert vezel.meti_sanction_risk is True

    note = next(lot for lot in lots if lot.make == "Nissan")
    assert note.model == "Note"
    assert note.frame_id == "HE12-389104"
    assert note.turnkey_cost_rub == 980000
    assert note.verdict == "green"
    assert note.fuel_type == "hybrid"
    assert note.meti_sanction_risk is True


@pytest.mark.django_db
def test_corolla_starter_lot_has_full_related_data(api_client: Client) -> None:
    response = api_client.post(
        "/api/v1/auth/register",
        {"email": "detail@example.com", "password": "Password123!"},
        content_type="application/json",
    )
    assert response.status_code == 201
    user_id = response.json()["user"]["user_id"]

    corolla = Lot.objects.get(user_id=user_id, make="Toyota")

    assert corolla.defects.count() == 4
    door_defect = corolla.defects.get(panel_id="front_left_door")
    assert door_defect.raw_code == "XX"
    assert door_defect.severity is None

    assert corolla.risk_flags.panel_replaced_xx is True
    assert corolla.risk_flags.pillar_or_frame_repair is False

    verdict = corolla.verdict_detail
    assert verdict.verdict == "green"
    assert verdict.net_benefit_rub == 415101
    assert len(verdict.reasoning_bullets) == 3

    market = corolla.market_info
    assert market.market_price_rf_rub == 1520000
    assert market.analogs_count == 14

    audit = corolla.cross_audit
    assert audit.status == "clean"
    assert audit.risk_level == "CLEAN"
    assert audit.history.count() == 1
    assert audit.anomalies.count() == 0

    checklist = corolla.safety_checklist
    assert checklist.overall_status == "ok"
    assert checklist.items.count() == 5

    customs = corolla.customs_calc
    assert customs.age_corridor == "3_to_5_years"
    assert customs.customs_duty_rub == 193154
    assert customs.utilization_fee_rub == 5200
    assert customs.rates_snapshot.eur_rub_cbrf == 95.0

    repair = corolla.farpost_repair
    assert repair.parts.count() == 1
    assert repair.service_works.count() == 3
    assert repair.grand_total_repair_rub == 31000
    paint_work = repair.service_works.get(work_type="paint")
    assert paint_work.amount_rub == 0
    assert paint_work.zero_cost_reason_ru == "не требуется"

    ladder = corolla.wise_cost_ladder
    assert ladder.turnkey_cost_rub == 1104899
    assert ladder.steps.count() == 7
    step_sum = sum(step.amount_rub for step in ladder.steps.all())
    assert step_sum == ladder.turnkey_cost_rub


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
