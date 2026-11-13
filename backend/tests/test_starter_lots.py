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

    note = next(lot for lot in lots if lot.make == "Nissan")
    assert note.model == "Note"
    assert note.frame_id == "HE12-389104"
    assert note.turnkey_cost_rub == 980000
    assert note.verdict == "green"


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
