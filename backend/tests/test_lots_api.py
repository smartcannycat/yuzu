import threading
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pillow_heif
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client, override_settings
from PIL import Image

from apps.core.enums import BatchStatus, PartSourceKind, PowerHpSource, UtilFeeType
from apps.integrations.currency.domain import BaseRates, CurrencyRatesResult, RatesOrigin
from apps.integrations.drom.schemas import DromMarketResult
from apps.integrations.ml.parser import MlServiceParser
from apps.lots.media import render_browser_scan_and_thumbnail
from apps.lots.models import Batch, BatchItem, DamagedPartItem, Lot
from apps.lots.pipeline import run_batch_pipeline
from apps.lots.pipeline.batches import append_items_to_batch, enqueue_batch


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
        lot_id = item["lot_id"]
        assert item["thumbnail_url"] == f"/api/v1/lots/{lot_id}/media/thumbnail"
        assert item["verdict_headline"] in {
            "РЕКОМЕНДОВАНО К ПОКУПКЕ",
            "ВНИМАНИЕ: ЕСТЬ НЮАНСЫ",
            "ПОКУПКУ НЕ РЕКОМЕНДУЕМ",
        }

    filtered = api_client.get("/api/v1/lots?make=Honda&verdict=yellow", **headers)
    assert filtered.status_code == 200
    assert filtered.json()["pagination"]["total_items"] == 1
    assert filtered.json()["items"][0]["frame_id"] == "RV3-1005521"
    assert filtered.json()["items"][0]["verdict_headline"] == "ВНИМАНИЕ: ЕСТЬ НЮАНСЫ"


@pytest.mark.django_db
def test_lot_detail_isolates_users_and_exposes_media_links(api_client: Client) -> None:
    headers_a, user_a_id = _register_and_auth(api_client, "a@example.com")
    headers_b, _ = _register_and_auth(api_client, "b@example.com")

    lot = Lot.objects.get(user_id=user_a_id, frame_id="RV3-1005521")
    detail_res = api_client.get(f"/api/v1/lots/{lot.id}", **headers_a)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["lot_id"] == str(lot.id)
    assert detail["media"]["sheet_thumbnail_url"] == f"/api/v1/lots/{lot.id}/media/thumbnail"
    assert detail["media"]["sheet_scan_url"] == f"/api/v1/lots/{lot.id}/media/scan"
    assert detail["economics"]["customs"]["util_fee_type"] == UtilFeeType.PERSONAL

    foreign_res = api_client.get(f"/api/v1/lots/{lot.id}", **headers_b)
    assert foreign_res.status_code == 404


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_authenticated_media_endpoint_and_no_public_media_route(api_client: Client) -> None:
    headers_a, user_a_id = _register_and_auth(api_client, "media-a@example.com")
    headers_b, _ = _register_and_auth(api_client, "media-b@example.com")

    lot = Lot.objects.get(user_id=user_a_id, frame_id="RV3-1005521")

    # Public /media/* route is removed even in DEBUG mode.
    public_media = api_client.get(f"/media/{lot.sheet_scan.name}")
    assert public_media.status_code == 404

    # Unauthenticated request returns 401 ProblemDetail.
    unauth = api_client.get(f"/api/v1/lots/{lot.id}/media/scan")
    assert unauth.status_code == 401
    assert unauth.headers["Content-Type"].startswith("application/problem+json")

    # Foreign user receives 404 ProblemDetail.
    foreign = api_client.get(f"/api/v1/lots/{lot.id}/media/scan", **headers_b)
    assert foreign.status_code == 404
    assert foreign.headers["Content-Type"].startswith("application/problem+json")

    # Invalid media kind returns 422 ProblemDetail.
    bad_kind = api_client.get(f"/api/v1/lots/{lot.id}/media/original", **headers_a)
    assert bad_kind.status_code == 422

    # Owner gets scan and thumbnail with strict security headers.
    for kind in ("scan", "thumbnail"):
        resp = api_client.get(f"/api/v1/lots/{lot.id}/media/{kind}", **headers_a)
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/jpeg"
        assert resp.headers["Cache-Control"] == "private, no-store"
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["Content-Security-Policy"] == "sandbox; default-src 'none'"
        assert resp.headers["Content-Disposition"] == f'inline; filename="lot-{kind}.jpg"'
        assert b"".join(resp.streaming_content).startswith(b"\xff\xd8\xff")

    # Incomplete or soft-deleted lots return 404.
    incomplete = Lot.objects.create(user_id=user_a_id, make="Honda", model="Fit")
    assert (
        api_client.get(f"/api/v1/lots/{incomplete.id}/media/scan", **headers_a).status_code == 404
    )

    api_client.delete(f"/api/v1/lots/{lot.id}", **headers_a)
    assert api_client.get(f"/api/v1/lots/{lot.id}/media/scan", **headers_a).status_code == 404


@pytest.mark.django_db
def test_damaged_part_source_kind_coerces_empty_legacy_value(api_client: Client) -> None:
    headers, user_id = _register_and_auth(api_client, "parts@example.com")
    lot = Lot.objects.get(user_id=user_id, frame_id="GB5-3179736")
    DamagedPartItem.objects.filter(repair__lot=lot).update(source_kind="")

    detail_res = api_client.get(f"/api/v1/lots/{lot.id}", **headers)
    assert detail_res.status_code == 200
    parts = detail_res.json()["economics"]["farpost_repair"]["parts"]
    assert parts
    assert all(part["source_kind"] == PartSourceKind.MATRIX for part in parts)


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
    assert payload["customs"]["util_fee_type"] == UtilFeeType.COMMERCIAL
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
def test_batch_upload_validation_and_append_conflicts(
    api_client: Client,
    settings,
) -> None:
    headers, _ = _register_and_auth(api_client, "upload@example.com")

    bad_file = SimpleUploadedFile("notes.txt", b"not an image", content_type="text/plain")
    assert (
        api_client.post("/api/v1/lots/batches", {"files": [bad_file]}, **headers).status_code == 400
    )

    # Extension/MIME mismatch and spoofed magic bytes must both be rejected.
    png_bytes = _make_png_bytes((200, 200), mode="RGB")
    ext_mime_mismatch = SimpleUploadedFile("sheet.jpg", png_bytes, content_type="text/plain")
    assert (
        api_client.post(
            "/api/v1/lots/batches", {"files": [ext_mime_mismatch]}, **headers
        ).status_code
        == 400
    )

    bad_ext = SimpleUploadedFile("sheet.txt", png_bytes, content_type="image/png")
    assert (
        api_client.post("/api/v1/lots/batches", {"files": [bad_ext]}, **headers).status_code == 400
    )

    spoofed_svg = SimpleUploadedFile(
        "evil.jpg",
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        content_type="image/jpeg",
    )
    assert (
        api_client.post("/api/v1/lots/batches", {"files": [spoofed_svg]}, **headers).status_code
        == 400
    )

    empty_file = SimpleUploadedFile("empty.png", b"", content_type="image/png")
    assert (
        api_client.post("/api/v1/lots/batches", {"files": [empty_file]}, **headers).status_code
        == 400
    )

    oversized_side = SimpleUploadedFile(
        "wide.png",
        _make_png_bytes((12001, 4), mode="RGB"),
        content_type="image/png",
    )
    assert (
        api_client.post("/api/v1/lots/batches", {"files": [oversized_side]}, **headers).status_code
        == 400
    )

    with patch("apps.lots.pipeline.batches._schedule_batch_pipeline"):
        files = [
            SimpleUploadedFile("../../traversal/sheet.png", png_bytes, content_type="image/png")
        ]
        created = api_client.post("/api/v1/lots/batches", {"files": files}, **headers)
        assert created.status_code == 202
        batch_id = created.json()["batch_id"]

        item = BatchItem.objects.get(batch_id=batch_id)
        assert item.original_filename == "sheet.png"
        assert ".." not in item.original_file.name
        assert item.original_file.name.endswith(".png")
        assert Path(item.original_file.path).is_relative_to(Path(settings.PRIVATE_INTAKE_ROOT))
        assert not Path(item.original_file.path).is_relative_to(Path(settings.MEDIA_ROOT))
        with pytest.raises(ValueError, match="not accessible via a URL"):
            _ = item.original_file.url

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
        conflict_files = [SimpleUploadedFile("sheet3.png", png_bytes, content_type="image/png")]
        conflict = api_client.post(
            f"/api/v1/lots/batches/{batch_id}/items",
            {"files": conflict_files},
            **headers,
        )
        assert conflict.status_code == 409


@pytest.mark.django_db
def test_batch_upload_cleans_saved_files_on_rollback(api_client: Client, settings) -> None:
    headers, _ = _register_and_auth(api_client, "rollback@example.com")
    png_bytes = _make_png_bytes((128, 128), mode="RGB")
    files = [
        SimpleUploadedFile("first.png", png_bytes, content_type="image/png"),
        SimpleUploadedFile("second.png", png_bytes, content_type="image/png"),
    ]
    orig_save = BatchItem.save
    call_count = 0

    def failing_second_save(self, *args, **kwargs):
        nonlocal call_count
        if kwargs.get("update_fields") == ["original_file", "updated_at"]:
            call_count += 1
            if call_count == 2:
                raise IntegrityError("simulated mid-batch DB failure")
        return orig_save(self, *args, **kwargs)

    with patch.object(BatchItem, "save", failing_second_save):
        resp = api_client.post("/api/v1/lots/batches", {"files": files}, **headers)

    assert resp.status_code == 500
    assert BatchItem.objects.count() == 0
    private_files = [p for p in Path(settings.PRIVATE_INTAKE_ROOT).rglob("*") if p.is_file()]
    assert private_files == []


@pytest.mark.django_db(transaction=True)
def test_batch_upload_cleans_saved_files_on_outer_atomic_rollback(
    user_factory,
    settings,
) -> None:
    user = user_factory(email="outer-rollback@example.com")
    png_bytes = _make_png_bytes((128, 128), mode="RGB")

    with (
        patch("apps.lots.pipeline.batches._schedule_batch_pipeline"),
        pytest.raises(RuntimeError, match="outer enqueue rollback"),
        transaction.atomic(),
    ):
        enqueue_batch(
            user,
            [
                SimpleUploadedFile("a.png", png_bytes, content_type="image/png"),
                SimpleUploadedFile("b.png", png_bytes, content_type="image/png"),
            ],
        )
        saved_during_tx = [p for p in Path(settings.PRIVATE_INTAKE_ROOT).rglob("*") if p.is_file()]
        assert len(saved_during_tx) == 2
        raise RuntimeError("outer enqueue rollback")

    assert Batch.objects.filter(user=user).count() == 0
    assert [p for p in Path(settings.PRIVATE_INTAKE_ROOT).rglob("*") if p.is_file()] == []

    # Committed batch stays on disk; a subsequent rolled-back append cleans only the new upload.
    with patch("apps.lots.pipeline.batches._schedule_batch_pipeline"):
        committed_batch = enqueue_batch(
            user,
            [SimpleUploadedFile("kept.png", png_bytes, content_type="image/png")],
        )
    kept_path = Path(committed_batch.items.get().original_file.path)
    assert kept_path.is_file()

    with (
        patch("apps.lots.pipeline.batches._schedule_batch_pipeline"),
        pytest.raises(RuntimeError, match="outer append rollback"),
        transaction.atomic(),
    ):
        append_items_to_batch(
            user,
            committed_batch.id,
            [SimpleUploadedFile("reverted.png", png_bytes, content_type="image/png")],
        )
        raise RuntimeError("outer append rollback")

    remaining = [p for p in Path(settings.PRIVATE_INTAKE_ROOT).rglob("*") if p.is_file()]
    assert remaining == [kept_path]


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

    with patch("apps.lots.pipeline.batches._schedule_batch_pipeline"):
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
        patch("apps.lots.pipeline.stages._PIPELINE_STEP_DELAY_SEC", 0),
        patch("apps.lots.pipeline.parallel.import_string", return_value=_FakeParser),
        patch(
            "apps.lots.pipeline.stages.AleadoCrossAuditService.audit_lot",
            side_effect=RuntimeError("offline"),
        ),
        patch("apps.lots.pipeline.stages.DromMarketService.evaluate", return_value=drom_result),
        patch("apps.lots.pipeline.stages.build_currency_service") as mock_curr,
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
        assert item["summary"]["thumbnail_url"] == f"/api/v1/lots/{lot_id}/media/thumbnail"
        assert item["summary"]["verdict_headline"] in {
            "РЕКОМЕНДОВАНО К ПОКУПКЕ",
            "ВНИМАНИЕ: ЕСТЬ НЮАНСЫ",
            "ПОКУПКУ НЕ РЕКОМЕНДУЕМ",
        }
        detail_res = api_client.get(f"/api/v1/lots/{lot_id}", **headers)
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["media"]["sheet_scan_url"] == f"/api/v1/lots/{lot_id}/media/scan"
        assert detail["media"]["sheet_thumbnail_url"] == f"/api/v1/lots/{lot_id}/media/thumbnail"


def test_render_browser_scan_and_thumbnail_resizes_and_transcodes_heic() -> None:
    scan_bytes, thumb_bytes = render_browser_scan_and_thumbnail(_make_heic_bytes((3000, 2000)))
    with Image.open(BytesIO(scan_bytes)) as scan_img, Image.open(BytesIO(thumb_bytes)) as thumb_img:
        assert scan_img.format == "JPEG"
        assert max(scan_img.size) == 2400
        assert thumb_img.format == "JPEG"
        assert max(thumb_img.size) == 480


def test_render_browser_scan_rejects_oversized_dimensions() -> None:
    with pytest.raises(Image.DecompressionBombError):
        render_browser_scan_and_thumbnail(_make_png_bytes((12001, 4), mode="RGB"))
