"""Tests for lot lifecycle transitions, Beat archiving, read-time consistency, and filters."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from tests.test_lots_api import _register_and_auth

from apps.core.enums import LotArchiveReason, TrafficLightColor
from apps.lots.lifecycle import compute_lot_expires_at
from apps.lots.models import (
    CrossAuditReport,
    CurrencyRatesSnapshot,
    CustomsCalculation,
    FarpostRepairSummary,
    Lot,
    LotRiskFlags,
    MarketComparisonInfo,
    SafetyChecklist,
    TrafficLightVerdict,
    WiseCostLadder,
)
from apps.lots.tasks import archive_expired_lots_task

if TYPE_CHECKING:
    from django.test import Client


def _create_complete_lot(
    user_id: str,
    *,
    make: str,
    model: str,
    verdict: TrafficLightColor,
    is_archived: bool = False,
    expires_at: datetime | None = None,
    auto_archive_disabled: bool = False,
) -> Lot:
    now = timezone.now()
    lot = Lot.objects.create(
        user_id=user_id,
        completed_at=now,
        make=make,
        model=model,
        frame_id=f"{model.upper()}-100001",
        lot_number="101",
        auction_house="USS",
        overall_grade="4",
        turnkey_cost_rub=1_500_000,
        market_price_rf_rub=1_800_000,
        net_benefit_rub=300_000,
        benefit_percentage=20.0,
        verdict=verdict,
        verdict_headline="РЕКОМЕНДОВАНО К ПОКУПКЕ",
        is_archived=is_archived,
        archived_at=now if is_archived else None,
        archived_reason=LotArchiveReason.MANUAL if is_archived else None,
        expires_at=expires_at,
        auto_archive_disabled=auto_archive_disabled,
    )
    LotRiskFlags.objects.create(lot=lot)
    TrafficLightVerdict.objects.create(
        lot=lot,
        verdict=verdict,
        headline="РЕКОМЕНДОВАНО К ПОКУПКЕ",
        short_verdict_label="РЕКОМЕНДОВАНО К ПОКУПКЕ",
        badge_text="Выгода: +300 000 ₽",
        net_benefit_rub=300_000,
        benefit_percentage=20.0,
        body_summary_ru="Без замечаний",
        interior_summary_ru="Оценка 4",
        reasoning_bullets=["Выгода +300 000 ₽"],
    )
    MarketComparisonInfo.objects.create(
        lot=lot,
        market_price_rf_rub=1_800_000,
        analogs_count=5,
        drom_search_url="https://auto.drom.ru/honda/fit/",
    )
    CrossAuditReport.objects.create(
        lot=lot,
        status="not_found",
        risk_level="INFO",
        headline_ru="Не найдено",
    )
    SafetyChecklist.objects.create(
        lot=lot,
        overall_status="ok",
        overall_label_ru="В норме",
    )
    customs = CustomsCalculation.objects.create(
        lot=lot,
        age_corridor="3_to_5_years",
        engine_cc=1_500,
        customs_duty_eur=2_550.0,
        customs_duty_rub=255_000,
        utilization_fee_rub=5_200,
        customs_clearance_fee_rub=8_530,
        freight_vladivostok_rub=95_000,
        broker_svh_sbkts_rub=99_000,
    )
    CurrencyRatesSnapshot.objects.create(
        customs=customs,
        jpy_rub_bank=0.55,
        eur_rub_cbrf=100.0,
        usd_rub_cbrf=90.0,
        cbrf_date="15.11.2026",
    )
    FarpostRepairSummary.objects.create(
        lot=lot,
        total_parts_from_rub=0,
        total_works_rub=0,
        grand_total_repair_rub=0,
        has_color_matched_parts=False,
    )
    WiseCostLadder.objects.create(
        lot=lot,
        car_bid_jpy=1_500_000,
        car_bid_rub=825_000,
        turnkey_cost_rub=1_500_000,
        market_price_rf_rub=1_800_000,
        net_benefit_rub=300_000,
        benefit_percentage=20.0,
    )
    return lot


def test_compute_lot_expires_at_jst_24h_and_3d_fallback() -> None:
    created = datetime(2026, 11, 10, 8, 30, 0, tzinfo=UTC)
    # 15.11.2026 23:59:59 JST (+09:00) + 24h -> 16.11.2026 23:59:59 JST == 16.11.2026 14:59:59 UTC
    assert compute_lot_expires_at(created, "15.11.2026") == datetime(
        2026, 11, 16, 14, 59, 59, tzinfo=UTC
    )
    # Invalid / missing auction_date falls back to created_at + 3 days
    assert compute_lot_expires_at(created, None) == created + timedelta(days=3)
    assert compute_lot_expires_at(created, "31.02.2026") == created + timedelta(days=3)
    assert compute_lot_expires_at(created, "not-a-date") == created + timedelta(days=3)


@pytest.mark.django_db
def test_get_endpoints_do_not_write_db_and_read_expired_lots_consistently(
    api_client: Client,
) -> None:
    headers, user_id = _register_and_auth(api_client, "lifecycle-read@example.com")
    now = timezone.now()
    expired_deadline = now - timedelta(hours=2)

    expired_lot = _create_complete_lot(
        user_id,
        make="Toyota",
        model="Aqua",
        verdict=TrafficLightColor.GREEN,
        expires_at=expired_deadline,
    )
    restored_lot = _create_complete_lot(
        user_id,
        make="Toyota",
        model="Prius",
        verdict=TrafficLightColor.GREEN,
        expires_at=expired_deadline,
        auto_archive_disabled=True,
    )

    with CaptureQueriesContext(connection) as ctx:
        active_res = api_client.get("/api/v1/lots?lifecycle=active", **headers)
        archived_res = api_client.get("/api/v1/lots?lifecycle=archived", **headers)
        detail_res = api_client.get(f"/api/v1/lots/{expired_lot.id}", **headers)

    assert active_res.status_code == 200
    assert archived_res.status_code == 200
    assert detail_res.status_code == 200

    write_queries = [
        q["sql"]
        for q in ctx.captured_queries
        if q["sql"].lstrip().upper().startswith(("UPDATE", "INSERT", "DELETE"))
    ]
    assert write_queries == []

    # Active tab includes 3 starter lots + restored_lot, excludes expired_lot.
    active_ids = {item["lot_id"] for item in active_res.json()["items"]}
    assert str(restored_lot.id) in active_ids
    assert str(expired_lot.id) not in active_ids
    assert active_res.json()["available_filters"]["archived_lots_count"] == 1

    # Archived tab shows expired_lot with consistent archive metadata before Beat sweeps it.
    archived_items = archived_res.json()["items"]
    assert len(archived_items) == 1
    assert archived_items[0]["lot_id"] == str(expired_lot.id)
    assert archived_items[0]["is_archived"] is True
    assert archived_items[0]["archived_reason"] == LotArchiveReason.EXPIRED
    assert archived_items[0]["archived_at"] is not None

    # Detail endpoint matches list summary archive state.
    detail_body = detail_res.json()
    assert detail_body["is_archived"] is True
    assert detail_body["archived_reason"] == LotArchiveReason.EXPIRED
    assert detail_body["archived_at"] == archived_items[0]["archived_at"]

    # DB row wasn't mutated on GET; now Beat task archives expired_lot only.
    expired_lot.refresh_from_db()
    assert expired_lot.is_archived is False

    swept = archive_expired_lots_task()
    assert swept == 1
    expired_lot.refresh_from_db()
    restored_lot.refresh_from_db()
    assert expired_lot.is_archived is True
    assert expired_lot.archived_reason == LotArchiveReason.EXPIRED
    assert restored_lot.is_archived is False


@pytest.mark.django_db
def test_available_filters_total_lots_count_invariant_across_verdict_and_facets(
    api_client: Client,
) -> None:
    headers, user_id = _register_and_auth(api_client, "filters-all@example.com")
    _create_complete_lot(
        user_id,
        make="Toyota",
        model="Aqua",
        verdict=TrafficLightColor.GREEN,
    )
    _create_complete_lot(
        user_id,
        make="Nissan",
        model="Note",
        verdict=TrafficLightColor.GREEN,
        is_archived=True,
    )

    # Starter lots (2 red + 1 yellow) + 1 active green = 4 active, 1 archived, 5 total.
    for verdict in ("green", "yellow", "red"):
        res = api_client.get(f"/api/v1/lots?lifecycle=active&verdict={verdict}", **headers)
        assert res.status_code == 200
        body = res.json()
        assert body["available_filters"]["total_lots_count"] == 4
        assert body["available_filters"]["archived_lots_count"] == 1

    make_filtered = api_client.get("/api/v1/lots?lifecycle=active&make=Toyota", **headers)
    assert make_filtered.status_code == 200
    assert make_filtered.json()["pagination"]["total_items"] == 1
    assert make_filtered.json()["available_filters"]["total_lots_count"] == 4

    archived_tab = api_client.get("/api/v1/lots?lifecycle=archived&verdict=red", **headers)
    assert archived_tab.status_code == 200
    assert archived_tab.json()["pagination"]["total_items"] == 0
    assert archived_tab.json()["available_filters"]["total_lots_count"] == 1

    all_tab = api_client.get("/api/v1/lots?lifecycle=all&verdict=green", **headers)
    assert all_tab.status_code == 200
    assert all_tab.json()["pagination"]["total_items"] == 2
    assert all_tab.json()["available_filters"]["total_lots_count"] == 5


@pytest.mark.django_db
def test_list_lots_enforces_max_length_100_on_query_make_model(api_client: Client) -> None:
    headers, _ = _register_and_auth(api_client, "maxlen@example.com")
    ok_val = "a" * 100
    too_long = "a" * 101

    for param in ("query", "make", "model"):
        ok_resp = api_client.get(f"/api/v1/lots?{param}={ok_val}", **headers)
        assert ok_resp.status_code == 200

        bad_resp = api_client.get(f"/api/v1/lots?{param}={too_long}", **headers)
        assert bad_resp.status_code == 422
        assert bad_resp.headers["Content-Type"].startswith("application/problem+json")
