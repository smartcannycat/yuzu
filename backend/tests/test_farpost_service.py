"""Repair calculation, cache provenance and atomic pipeline persistence."""

import time
from dataclasses import replace
from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.db import IntegrityError, connection
from django.utils import timezone

from apps.core.enums import ExternalCacheSource, FuelType, ItemProcessingStatus, WorkType
from apps.core.models import ExternalCache
from apps.lots import pipeline
from apps.lots.integrations.farpost import service as farpost_service
from apps.lots.integrations.farpost.client import (
    FarpostFetchError,
    FarpostRateLimitedError,
    PartCriteria,
    PartOffer,
)
from apps.lots.integrations.farpost.service import (
    _body_code,
    _cache_key,
    _search_model,
    estimate_repair,
    save_repair_estimate,
    search_cached,
)
from apps.lots.models import Batch, BatchItem, Lot, LotDefect, ServiceWorkItem
from apps.lots.queries import _build_farpost_out

CRITERIA = PartCriteria(
    "Toyota", "Corolla", "NRE210", "front_left_door", "дверь", "левая", "передняя", "070"
)
OFFER = PartOffer(
    "123", "https://www.farpost.ru/vladivostok/zapchasti/door-123.html", "Дверь", 18000, True
)


@pytest.fixture(autouse=True)
def _isolate_farpost_cooldown(monkeypatch):
    monkeypatch.setattr(farpost_service, "_local_cooldown_until", 0.0)
    monkeypatch.setattr(farpost_service, "get_redis_client", lambda: None)


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


@pytest.mark.django_db
def test_cache_ttl_negative_marker_and_stale_age():
    deadline = time.monotonic() + 20
    assert search_cached(source(), CRITERIA, deadline=deadline) == ([OFFER], False)
    assert search_cached(source(error=True), CRITERIA, deadline=deadline) == ([OFFER], False)
    key = _cache_key(CRITERIA)
    entry = ExternalCache.objects.get(key=key)
    assert timedelta(hours=5, minutes=59) < entry.expires_at - timezone.now() <= timedelta(hours=6)
    ExternalCache.objects.filter(key=key).update(expires_at=timezone.now() - timedelta(seconds=1))
    assert search_cached(source([]), CRITERIA, deadline=deadline) == ([], False)
    assert ExternalCache.objects.get(key=key).payload["offers"][0]["price_rub"] == 18000
    marker = ExternalCache.objects.get(key=key + ":empty")
    assert timedelta(minutes=9) < marker.expires_at - timezone.now() <= timedelta(minutes=10)
    assert search_cached(source(error=True), CRITERIA, deadline=deadline) == ([], False)
    ExternalCache.objects.filter(key=key + ":empty").update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert search_cached(source(error=True), CRITERIA, deadline=deadline) == ([OFFER], True)
    ExternalCache.objects.filter(key=key).update(updated_at=timezone.now() - timedelta(days=2))
    assert search_cached(source(error=True), CRITERIA, deadline=deadline) == ([], True)
    ExternalCache.objects.filter(key=key).update(payload={"offers": [{"price_rub": "bad"}]})
    assert search_cached(source(error=True), CRITERIA, deadline=deadline) == ([], True)


@pytest.mark.django_db
def test_cached_fallback_does_not_claim_stock_or_color(lot):
    defect(lot, "X")
    estimate_repair(lot, client=source())
    ExternalCache.objects.filter(source=ExternalCacheSource.FARPOST).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    result = estimate_repair(lot, client=source(error=True))
    assert result.parts[0].price_from_rub == 18000
    assert not result.parts[0].in_stock_vladivostok
    assert result.parts[0].is_statistical_fallback
    assert not result.has_color_matched_parts
    assert result.total_works_rub == 12500


@pytest.mark.django_db
def test_save_idempotence_and_api_contract(lot):
    defect(lot, "X")
    for _ in range(2):
        summary = save_repair_estimate(lot, client=source())
    assert summary.parts.count() == 1
    assert summary.service_works.count() == 2
    payload = _build_farpost_out(summary).model_dump()
    assert "https://" not in str(payload) and "farpost_url" not in str(payload)
    assert (
        payload["grand_total_repair_rub"]
        == payload["total_parts_from_rub"] + payload["total_works_rub"]
    )
    assert "уже включена" not in payload["included_in_turnkey_hint_ru"]


@pytest.mark.django_db
def test_failed_write_rolls_back_previous_summary(lot, monkeypatch):
    defect(lot, "X")
    summary = save_repair_estimate(lot, client=source())

    def fail(*args, **kwargs):
        raise IntegrityError("forced write failure")

    monkeypatch.setattr(ServiceWorkItem.objects, "bulk_create", fail)
    with pytest.raises(IntegrityError):
        save_repair_estimate(lot, client=source())
    summary.refresh_from_db()
    assert summary.parts.count() == 1 and summary.service_works.count() == 2
    assert summary.grand_total_repair_rub == 20500


@pytest.mark.django_db(transaction=True)
def test_http_is_outside_write_transaction(lot):
    defect(lot, "X")
    client = source()

    def search(*args, **kwargs):
        assert not connection.in_atomic_block
        return [OFFER]

    client.search.side_effect = search
    save_repair_estimate(lot, client=client)


@pytest.mark.django_db
def test_pipeline_persists_fallback_without_failing_batch(lot, monkeypatch):
    defect(lot, "X")
    batch = Batch.objects.create(user=lot.user)
    item = BatchItem.objects.create(
        batch=batch, lot=lot, file_index=0, original_filename="sheet.jpg"
    )
    monkeypatch.setattr(
        "apps.lots.integrations.farpost.service.FarpostClient", lambda **_kw: source(error=True)
    )
    assert pipeline._step_farpost_parts(item)
    assert lot.farpost_repair.parts.get().is_statistical_fallback
    item.refresh_from_db()
    assert item.status != ItemProcessingStatus.FAILED


@pytest.mark.django_db
def test_structured_severity_is_used_when_raw_code_has_no_grade(lot):
    item = defect(lot, "U")
    item.severity = 1
    item.save(update_fields=["severity"])
    assert estimate_repair(lot, client=source()).total_works_rub == 2500


@pytest.mark.django_db
def test_structured_replacement_without_raw_code(lot):
    item = defect(lot, "")
    item.defect_types = ["XX"]
    item.severity = 3
    item.save(update_fields=["defect_types", "severity"])
    assert estimate_repair(lot, client=source()).total_parts_from_rub == 18000


@pytest.mark.django_db
def test_failed_source_does_not_expand_into_another_network_request(lot):
    defect(lot, "X")
    client = source(error=True)
    estimate_repair(lot, client=client)
    assert client.search.call_count == 1


@pytest.mark.django_db
def test_existing_detail_endpoint_exposes_saved_estimate(user_factory, api_client):
    from ninja_jwt.tokens import RefreshToken

    from apps.lots.starter_lots import seed_starter_lots

    user = user_factory()
    seed_starter_lots(user)
    vehicle = Lot.objects.get(user=user, make="Toyota")
    save_repair_estimate(vehicle, client=source(error=True))
    token = str(RefreshToken.for_user(user).access_token)
    response = api_client.get(f"/api/v1/lots/{vehicle.pk}", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 200
    repair = response.json()["economics"]["farpost_repair"]
    assert repair["parts"][0]["is_statistical_fallback"]
    assert (
        repair["grand_total_repair_rub"]
        == repair["total_parts_from_rub"] + repair["total_works_rub"]
    )
    assert "farpost_url" not in str(repair)


@pytest.mark.django_db
def test_existing_economics_includes_saved_repair_exactly_once(user_factory):
    from apps.lots.economics import recompute_lot_economics
    from apps.lots.starter_lots import seed_starter_lots

    user = user_factory()
    seed_starter_lots(user)
    vehicle = Lot.objects.get(user=user, make="Toyota")
    summary = save_repair_estimate(vehicle, client=source(error=True))
    recompute_lot_economics(vehicle, include_repairs=False)
    vehicle.refresh_from_db()
    without_repairs = vehicle.turnkey_cost_rub
    recompute_lot_economics(vehicle, include_repairs=True)
    vehicle.refresh_from_db()
    assert vehicle.turnkey_cost_rub - without_repairs == summary.grand_total_repair_rub
    recompute_lot_economics(vehicle, include_repairs=True)
    vehicle.refresh_from_db()
    assert vehicle.turnkey_cost_rub - without_repairs == summary.grand_total_repair_rub


@pytest.mark.django_db
def test_ml_compound_defects_shared_raw_code_do_not_duplicate_work(lot):
    first = defect(lot, "A2/W1")
    first.defect_types = ["A"]
    first.severity = 2
    first.save(update_fields=["defect_types", "severity"])
    second = defect(lot, "A2/W1")
    second.defect_types = ["W"]
    second.severity = 1
    second.save(update_fields=["defect_types", "severity"])
    client = source()
    result = estimate_repair(lot, client=client)
    assert len(result.service_works) == 1
    assert result.total_works_rub == 10000
    client.search.assert_not_called()


@pytest.mark.django_db
def test_body_code_and_model_normalization_support_single_digit_jdm_series(user_factory):
    freed = Lot.objects.create(
        user=user_factory(),
        make="Honda",
        model="Freed Hybrid",
        model_code="6BA-GB5",
        frame_id="GB5-3179736",
        paint_code="NH883P",
        fuel_type=FuelType.HYBRID,
    )
    assert _body_code(freed) == "GB5"
    assert _search_model(freed.model) == "Freed"
    fit = Lot(make="Honda", model="Fit", model_code="DBA-GE6", frame_id="")
    assert _body_code(fit) == "GE6"
    corolla = Lot(make="Toyota", model="Corolla", model_code="3BA-NRE210W", frame_id="")
    assert _body_code(corolla) == "NRE210W"


@pytest.mark.django_db
def test_validated_per_panel_fallback_prices(lot):
    defect(lot, "X", "windshield")
    defect(lot, "X", "front_left_fender")
    defect(lot, "X", "front_bumper")
    result = estimate_repair(lot, client=source([]))
    by_panel = {item.panel_id: item.price_from_rub for item in result.parts}
    assert by_panel == {
        "windshield": 7500,
        "front_left_fender": 12000,
        "front_bumper": 16000,
    }


@pytest.mark.django_db
def test_rate_limit_cooldown_stops_remaining_panel_requests(lot, monkeypatch):
    monkeypatch.setattr(farpost_service, "_local_cooldown_until", 0.0)
    monkeypatch.setattr(farpost_service, "get_redis_client", lambda: None)
    defect(lot, "X", "front_left_door")
    defect(lot, "X", "front_right_door")
    client = Mock()
    client.search.side_effect = FarpostRateLimitedError("verify redirect")
    result = estimate_repair(lot, client=client)
    assert client.search.call_count == 1
    assert len(result.parts) == 2
    assert all(p.is_statistical_fallback for p in result.parts)
