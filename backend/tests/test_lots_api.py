import threading
from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import patch

import pillow_heif
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from PIL import Image

from apps.core.enums import BatchStatus, PowerHpSource
from apps.lots.integrations.currency.domain import BaseRates, CurrencyRatesResult, RatesOrigin
from apps.lots.integrations.drom.schemas import DromMarketResult
from apps.lots.integrations.ml.parser import MlServiceParser
from apps.lots.media import render_browser_scan_and_thumbnail
from apps.lots.models import Batch, BatchItem, Lot
from apps.lots.pipeline import run_batch_pipeline


def _register_and_auth(
    client: Client, email: str = "buyer@example.com"
) -> tuple[dict[str, str], str]:
    response = client.post(
        "/api/v1/auth/register",
        {"email": email, "password": "StrongPass123!", "name": "Покупатель"},
        content_type="application/json",
    )
    assert response.status_code == 201
    data = response.json()
    headers = {"HTTP_AUTHORIZATION": f"Bearer {data['access_token']}"}
    return headers, data["user"]["user_id"]


def _make_png_bytes(size: tuple[int, int] = (800, 600), mode: str = "RGBA") -> bytes:
    img = Image.new(mode, size, (240, 245, 250, 255) if mode == "RGBA" else (240, 245, 250))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_heic_bytes(size: tuple[int, int] = (800, 600)) -> bytes:
    pillow_heif.register_heif_opener()
    img = Image.new("RGB", size, (220, 230, 240))
    buf = BytesIO()
    img.save(buf, format="HEIF")
    return buf.getvalue()


class _FakeParser:
    def gatekeeper(self, item: BatchItem) -> str | None:
        return None

    def fast_header(self, item: BatchItem) -> str | None:
        return "Honda Freed #10034"

    def parse(self, item: BatchItem) -> None:
        lot = item.lot
        assert lot is not None
        lot.lot_number = "10034"
        lot.auction_house = "MIRIVE"
        lot.auction_branch = "Saitama"
        lot.auction_strictness_index = 0.8
        lot.make = "Honda"
        lot.model = "Freed"
        lot.model_code = "DBA-GB5"
        lot.chassis_number = "GB5-1025108"
        lot.frame_id = "GB5-1025108"
        lot.frame_id_confidence = "exact"
        lot.first_reg_year = 2021
        lot.first_reg_month = 3
        lot.year = 2021
        lot.engine_cc = 1496
        lot.mileage_km = 45000
        lot.odometer_status = "confirmed"
        lot.transmission = "CVT"
        lot.drive_type = "2WD"
        lot.fuel_type = "gasoline"
        lot.overall_grade = "4"
        lot.save()


@pytest.mark.django_db
def test_lots_list_requires_auth_and_lists_starter_lots_with_media(api_client: Client) -> None:
    unauth = api_client.get("/api/v1/lots")
    assert unauth.status_code == 401

    headers, _ = _register_and_auth(api_client)
    res = api_client.get("/api/v1/lots", **headers)
    assert res.status_code == 200
    body = res.json()

    assert body["pagination"]["total_items"] == 3
    assert len(body["items"]) == 3
    for item in body["items"]:
        assert item["thumbnail_url"]
        assert item["thumbnail_url"].startswith("/media/")
        assert item["thumbnail_url"].endswith(".jpg")

    filtered = api_client.get("/api/v1/lots?make=Honda&verdict=yellow", **headers)
    assert filtered.status_code == 200
    assert filtered.json()["pagination"]["total_items"] == 1
    assert filtered.json()["items"][0]["frame_id"] == "RV3-1005521"


@pytest.mark.django_db
def test_lot_detail_isolates_users_and_exposes_media_links(api_client: Client) -> None:
    headers_a, user_a_id = _register_and_auth(api_client, "a@example.com")
    headers_b, _ = _register_and_auth(api_client, "b@example.com")

    lot = Lot.objects.get(user_id=user_a_id, frame_id="RV3-1005521")
    detail_res = api_client.get(f"/api/v1/lots/{lot.id}", **headers_a)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["lot_id"] == str(lot.id)
    assert detail["media"]["sheet_thumbnail_url"].startswith("/media/")
    assert detail["media"]["sheet_scan_url"].startswith("/media/")

    foreign_res = api_client.get(f"/api/v1/lots/{lot.id}", **headers_b)
    assert foreign_res.status_code == 404


@pytest.mark.django_db
def test_recalculate_updates_economics_and_rejects_deleted_or_incomplete_lots(
    api_client: Client,
) -> None:
    headers, user_id = _register_and_auth(api_client, "recalc@example.com")
    lot = Lot.objects.get(user_id=user_id, frame_id="RV3-1005521")

    ok = api_client.post(
        f"/api/v1/lots/{lot.id}/recalculate",
        {
            "bid_jpy": 950000,
            "is_commercial_util": True,
            "include_repairs": False,
            "custom_power_hp": 170,
            "custom_freight_rub": 110000,
        },
        content_type="application/json",
        **headers,
    )
    assert ok.status_code == 200
    payload = ok.json()
    assert payload["applied_bid_jpy"] == 950000
    assert payload["is_commercial_util"] is True
    assert payload["include_repairs"] is False
    assert payload["customs"]["freight_vladivostok_rub"] == 110000
    assert payload["is_simulation_modified"] is True

    # Reload detail (simulating F5): persisted state retains modification flag.
    reloaded = api_client.get(f"/api/v1/lots/{lot.id}", **headers)
    assert reloaded.status_code == 200
    assert reloaded.json()["economics"]["is_simulation_modified"] is True

    # Reset restores the persisted DB baseline (survives subsequent F5).
    reset_res = api_client.post(f"/api/v1/lots/{lot.id}/recalculate/reset", **headers)
    assert reset_res.status_code == 200
    reset_payload = reset_res.json()
    assert reset_payload["is_simulation_modified"] is False
    assert reset_payload["pdf_report_stale"] is False
    assert reset_payload["is_commercial_util"] is False
    assert reset_payload["include_repairs"] is True
    assert reset_payload["applied_bid_jpy"] == lot.wise_cost_ladder.car_bid_jpy
    assert reset_payload["turnkey_cost_rub"] == lot.turnkey_cost_rub

    reloaded_after_reset = api_client.get(f"/api/v1/lots/{lot.id}", **headers)
    assert reloaded_after_reset.status_code == 200
    assert reloaded_after_reset.json()["economics"]["is_simulation_modified"] is False
    assert (
        reloaded_after_reset.json()["economics"]["wise_cost_ladder"]["turnkey_cost_rub"]
        == lot.turnkey_cost_rub
    )

    # Incomplete lot (still processing) must not be recalculable.
    incomplete = Lot.objects.create(user_id=user_id, make="Honda", model="Fit")
    res_incomplete = api_client.post(
        f"/api/v1/lots/{incomplete.id}/recalculate",
        {"bid_jpy": 500000},
        content_type="application/json",
        **headers,
    )
    assert res_incomplete.status_code == 404

    # Soft-deleted lot must also return 404 on recalculate.
    del_res = api_client.delete(f"/api/v1/lots/{lot.id}", **headers)
    assert del_res.status_code == 204
    res_deleted = api_client.post(
        f"/api/v1/lots/{lot.id}/recalculate",
        {"bid_jpy": 950000},
        content_type="application/json",
        **headers,
    )
    assert res_deleted.status_code == 404


@pytest.mark.django_db
def test_lot_lifecycle_patch_and_bulk_delete(api_client: Client) -> None:
    headers, user_id = _register_and_auth(api_client, "lifecycle@example.com")
    other_headers, other_id = _register_and_auth(api_client, "other@example.com")

    lots = list(Lot.objects.filter(user_id=user_id).order_by("created_at"))
    other_lot = Lot.objects.filter(user_id=other_id).first()
    assert other_lot is not None

    patch_res = api_client.patch(
        f"/api/v1/lots/{lots[0].id}",
        {"is_archived": True},
        content_type="application/json",
        **headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["is_archived"] is True
    assert patch_res.json()["archived_reason"] == "manual"

    active_list = api_client.get("/api/v1/lots?lifecycle=active", **headers)
    assert active_list.json()["pagination"]["total_items"] == 2
    assert active_list.json()["available_filters"]["archived_lots_count"] == 1

    restore_res = api_client.patch(
        f"/api/v1/lots/{lots[0].id}",
        {"is_archived": False},
        content_type="application/json",
        **headers,
    )
    assert restore_res.status_code == 200
    assert restore_res.json()["is_archived"] is False
    lots[0].refresh_from_db()
    assert lots[0].auto_archive_disabled is True

    bulk_res = api_client.post(
        "/api/v1/lots/bulk-delete",
        {"lot_ids": [str(lots[0].id), str(lots[1].id), str(other_lot.id)]},
        content_type="application/json",
        **headers,
    )
    assert bulk_res.status_code == 200
    bulk_data = bulk_res.json()
    assert bulk_data["deleted_count"] == 2
    assert set(bulk_data["deleted_ids"]) == {str(lots[0].id), str(lots[1].id)}
    assert bulk_data["not_found_ids"] == [str(other_lot.id)]

    # Other user's lot stays untouched.
    assert api_client.get(f"/api/v1/lots/{other_lot.id}", **other_headers).status_code == 200


@pytest.mark.django_db
def test_batch_upload_validation_and_append_conflicts(api_client: Client) -> None:
    headers, _ = _register_and_auth(api_client, "upload@example.com")

    bad_file = SimpleUploadedFile("notes.txt", b"not an image", content_type="text/plain")
    bad_res = api_client.post("/api/v1/lots/batches", {"files": [bad_file]}, **headers)
    assert bad_res.status_code == 400

    png_bytes = _make_png_bytes((200, 200), mode="RGB")
    with patch("apps.lots.pipeline._schedule_batch_pipeline"):
        files = [SimpleUploadedFile("sheet.png", png_bytes, content_type="image/png")]
        created = api_client.post("/api/v1/lots/batches", {"files": files}, **headers)
        assert created.status_code == 202
        batch_id = created.json()["batch_id"]

        progress = api_client.get(f"/api/v1/lots/batches/{batch_id}", **headers)
        assert progress.status_code == 200
        assert progress.json()["total_count"] == 1

        extra = [SimpleUploadedFile("sheet2.png", png_bytes, content_type="image/png")]
        appended = api_client.post(
            f"/api/v1/lots/batches/{batch_id}/items",
            {"files": extra},
            **headers,
        )
        assert appended.status_code == 202
        assert appended.json()["total_count"] == 2

        Batch.objects.filter(id=batch_id).update(status=BatchStatus.COMPLETED)
        conflict = api_client.post(
            f"/api/v1/lots/batches/{batch_id}/items",
            {"files": extra},
            **headers,
        )
        assert conflict.status_code == 409


@pytest.mark.django_db(transaction=True)
def test_batch_pipeline_generates_browser_scan_and_thumbnail_for_png_and_heic(
    api_client: Client,
    settings,
) -> None:
    headers, _ = _register_and_auth(api_client, "pipeline@example.com")
    png_file = SimpleUploadedFile(
        "sheet.png",
        _make_png_bytes((1200, 900), mode="RGBA"),
        content_type="image/png",
    )
    heic_file = SimpleUploadedFile(
        "iphone.heic",
        _make_heic_bytes((1200, 900)),
        content_type="image/heic",
    )

    with patch("apps.lots.pipeline._schedule_batch_pipeline"):
        created = api_client.post(
            "/api/v1/lots/batches",
            {"files": [png_file, heic_file]},
            **headers,
        )
        assert created.status_code == 202
        batch_id = created.json()["batch_id"]

    settings.LOT_PARSER_BACKEND = f"{MlServiceParser.__module__}.{_FakeParser.__name__}"
    drom_result = DromMarketResult(
        market_price_rf_rub=1_550_000,
        analogs_count=6,
        price_min_rub=1_400_000,
        price_max_rub=1_700_000,
        search_region_ru="ДФО / Владивосток",
        excludes_under_order=True,
        filtered_out_under_order_count=1,
        is_fallback=False,
        fallback_reason_ru=None,
        drom_search_url="https://auto.drom.ru/honda/freed/",
        power_hp=131,
        power_hp_source=PowerHpSource.DROM_CATALOG,
        is_under_160_hp=True,
    )
    rates_result = CurrencyRatesResult(
        base=BaseRates(eur_rub=95.0, usd_rub=85.0, jpy_rub=0.568, cbrf_date="14.11.2026"),
        commercial_jpy_rub=0.585,
        jpy_rate_source="ЦБ РФ + спред",
        origin=RatesOrigin.LIVE,
        fetched_at=datetime.now(UTC),
        is_fallback=False,
    )

    with (
        patch("apps.lots.pipeline._PIPELINE_STEP_DELAY_SEC", 0),
        patch("apps.lots.pipeline.import_string", return_value=_FakeParser),
        patch(
            "apps.lots.pipeline.AleadoCrossAuditService.audit_lot",
            side_effect=RuntimeError("offline"),
        ),
        patch("apps.lots.services.DromMarketService.evaluate", return_value=drom_result),
        patch("apps.lots.pipeline.build_currency_service") as mock_curr,
    ):
        mock_curr.return_value.get_currency_rates.return_value = rates_result
        worker = threading.Thread(target=run_batch_pipeline, args=(batch_id,))
        worker.start()
        worker.join(timeout=15)
        assert not worker.is_alive()

    progress = api_client.get(f"/api/v1/lots/batches/{batch_id}", **headers)
    assert progress.status_code == 200
    progress_data = progress.json()
    assert progress_data["status"] == "completed"
    assert progress_data["ready_count"] == 2

    for item in progress_data["items"]:
        lot_id = item["lot_id"]
        assert item["summary"]["thumbnail_url"].endswith(".jpg")
        detail_res = api_client.get(f"/api/v1/lots/{lot_id}", **headers)
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["media"]["sheet_scan_url"].endswith(".jpg")
        assert detail["media"]["sheet_thumbnail_url"].endswith(".jpg")


def test_render_browser_scan_and_thumbnail_resizes_and_transcodes_heic() -> None:
    scan_bytes, thumb_bytes = render_browser_scan_and_thumbnail(_make_heic_bytes((3000, 2000)))
    with Image.open(BytesIO(scan_bytes)) as scan_img, Image.open(BytesIO(thumb_bytes)) as thumb_img:
        assert scan_img.format == "JPEG"
        assert max(scan_img.size) == 2400
        assert thumb_img.format == "JPEG"
        assert max(thumb_img.size) == 480
