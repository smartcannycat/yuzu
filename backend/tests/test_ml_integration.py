import json
from unittest.mock import patch

import httpx
import pytest
from django.core.files.base import ContentFile

from apps.core.enums import BodyPanel, ItemProcessingStatus, TaskStep
from apps.lots.integrations.ml.client import (
    MlServiceClient,
    MlServiceError,
    MlServiceUnavailableError,
)
from apps.lots.integrations.ml.parser import MlServiceParser
from apps.lots.models import Batch, BatchItem, Lot, LotDefect, LotRiskFlags


def _sheet_payload(**overrides: object) -> dict:
    payload: dict = {
        "lot_number": "5190",
        "auction_house": "USS",
        "auction_strictness_index": 4.5,
        "auction_branch": "Nagoya",
        "make": "Subaru",
        "model": "Forester",
        "trim": "XT",
        "model_code": "SJ5",
        "chassis_number": "SJ5-123456",
        "frame_id": "SJ5-123456",
        "frame_id_confidence": "exact",
        "first_reg_year": 2015,
        "first_reg_month": 6,
        "first_reg_date_str": "06.2015",
        "is_pass_corridor_3_5": True,
        "engine_cc": 1998,
        "mileage_km": 88000,
        "odometer_status": "confirmed",
        "transmission": "CVT",
        "drive_type": "4WD",
        "fuel_type": "gasoline",
        "color_ru": "Синий",
        "paint_code": "G1E",
        "overall_grade": "4",
        "exterior_grade": "3.5",
        "interior_grade": "B",
        "shaken_until": "2027-06",
        "recycling_fee_yen": 15000,
        "recycling_fee_paid": True,
        "equipment_ru": ["Климат-контроль", "Камера заднего вида"],
        "defects": [
            {
                "panel_id": "front_left_fender",
                "panel_ru": "Переднее левое крыло",
                "defect_types": ["A1"],
                "severity": 2,
                "description_ru": "Царапина",
                "raw_code": "A1",
            },
            {
                "panel_id": "rear_bumper",
                "panel_ru": "Задний бампер",
                "defect_types": ["B2", "W1"],
                "severity": 3,
                "description_ru": "Вмятина",
                "raw_code": "B2",
            },
        ],
        "risk_flags": {
            "is_flooded": True,
            "airbag_deployed": False,
            "hail_damage": False,
            "underbody_rust": True,
            "underbody_corrosion": False,
            "core_support_repair": False,
            "pillar_or_frame_repair": False,
            "panel_replaced_xx": False,
            "panel_needs_replacement_x": False,
            "odometer_issue": False,
            "color_changed": False,
            "windshield_damage": True,
            "repaired_grade_r_ra": False,
        },
        "inspector_notes_raw": ["note raw"],
        "inspector_notes_ru": ["Заметка инспектора"],
        "seller_comments_ru": ["Комментарий продавца"],
        "extra_ru": ["Дополнительно"],
        "ocr_warnings": ["Blurred corner"],
    }
    payload.update(overrides)
    return payload


def _parser_response_payload(**overrides: object) -> dict:
    payload: dict = {
        "status": "ok",
        "warnings": ["minor smudge"],
        "low_confidence_fields": ["trim"],
        "sheet": _sheet_payload(),
        "meta": {
            "processing_ms": 1234.5,
            "mode_used": "gemini-decision-1",
            "cached": False,
            "model_used": "gemini-2.0-flash",
            "sha256": "abc123",
            "unknown_future_field": 1,
        },
        "unknown_future_field": "ignored",
    }
    payload.update(overrides)
    return payload


def _ok_response_body(**overrides: object) -> bytes:
    return json.dumps(_parser_response_payload(**overrides), ensure_ascii=False).encode("utf-8")


def _rejected_response_body() -> bytes:
    return json.dumps(
        {
            "status": "rejected_not_sheet",
            "warnings": [],
            "low_confidence_fields": [],
            "sheet": None,
        },
        ensure_ascii=False,
    ).encode("utf-8")


def _transport(responder) -> httpx.MockTransport:
    return httpx.MockTransport(responder)


def _client(responder, *, api_key: str = "") -> MlServiceClient:
    return MlServiceClient(
        base_url="http://ml.test",
        timeout_sec=5.0,
        api_key=api_key,
        transport=_transport(responder),
    )


@pytest.fixture
def batch_item(user_factory, db):
    user = user_factory(email="ml-parser@example.com")
    batch = Batch.objects.create(user=user)
    lot = Lot.objects.create(user=user)
    item = BatchItem.objects.create(
        batch=batch,
        lot=lot,
        file_index=0,
        original_filename="sheet.png",
        status=ItemProcessingStatus.PROCESSING,
        current_step=TaskStep.GATEKEEPER,
    )
    item.original_file.save("sheet.png", ContentFile(b"fake-png-bytes"), save=True)
    item.refresh_from_db()
    return item


def test_parse_sheet_sends_multipart_and_api_key() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["api_key"] = request.headers.get("X-API-Key")
        seen["content_type"] = request.headers.get("Content-Type", "")
        seen["body"] = request.read()
        return httpx.Response(200, content=_ok_response_body())

    response = _client(handler, api_key="secret-key").parse_sheet(b"image-bytes", "sheet.png")

    assert seen["url"].startswith("http://ml.test/api/v1/sheets/parse")
    assert "force_refresh=false" in seen["url"]
    assert seen["api_key"] == "secret-key"
    assert "multipart/form-data" in seen["content_type"]
    assert b'filename="sheet.png"' in seen["body"]
    assert b"image/png" in seen["body"]
    assert response.status == "ok"
    assert response.sheet is not None
    assert response.sheet.make == "Subaru"
    assert response.meta.mode_used == "gemini-decision-1"


def test_parse_sheet_omits_api_key_header_when_not_configured() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["api_key"] = request.headers.get("X-API-Key")
        return httpx.Response(200, content=_ok_response_body())

    _client(handler).parse_sheet(b"image-bytes", "sheet.png")
    assert seen["api_key"] is None


def test_parse_sheet_maps_400_value_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"detail": "Unsupported file type"})

    with pytest.raises(ValueError, match="Unsupported file type"):
        _client(handler).parse_sheet(b"image-bytes", "sheet.png")


def test_parse_sheet_maps_503_and_timeout_to_unavailable() -> None:
    def unavailable(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "Model is warming up"})

    with pytest.raises(MlServiceUnavailableError, match="Model is warming up"):
        _client(unavailable).parse_sheet(b"image-bytes", "sheet.png")

    def timeout(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom")

    with pytest.raises(MlServiceUnavailableError):
        _client(timeout).parse_sheet(b"image-bytes", "sheet.png")


def test_parse_sheet_maps_unexpected_status_and_invalid_json() -> None:
    def server_error(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    with pytest.raises(MlServiceError):
        _client(server_error).parse_sheet(b"image-bytes", "sheet.png")

    def invalid_json(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json{")

    with pytest.raises(MlServiceError, match="invalid payload"):
        _client(invalid_json).parse_sheet(b"image-bytes", "sheet.png")


def test_parse_sheet_rejects_invalid_payload_types() -> None:
    body = json.dumps(
        {
            "status": "ok",
            "sheet": _sheet_payload(make=12345),
        }
    ).encode("utf-8")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with pytest.raises(MlServiceError, match="invalid payload"):
        _client(handler).parse_sheet(b"image-bytes", "sheet.png")


@pytest.mark.django_db
def test_full_flow_fills_lot_risk_flags_and_defects(batch_item) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, content=_ok_response_body())

    parser = MlServiceParser(client=_client(handler))

    rejection = parser.gatekeeper(batch_item)
    assert rejection is None

    preview_title = parser.fast_header(batch_item)
    assert preview_title == "Subaru Forester #5190"

    parser.parse(batch_item)

    # Exactly one HTTP call: gatekeeper did the heavy work.
    assert len(calls) == 1

    lot = batch_item.lot
    lot.refresh_from_db()
    assert lot.make == "Subaru"
    assert lot.model == "Forester"
    assert lot.trim == "XT"
    assert lot.year == 2015
    assert lot.auction_house == "USS"
    assert lot.auction_branch == "Nagoya"
    assert lot.auction_strictness_index == 4.5
    assert lot.lot_number == "5190"
    assert lot.model_code == "SJ5"
    assert lot.chassis_number == "SJ5-123456"
    assert lot.frame_id == "SJ5-123456"
    assert lot.frame_id_confidence == "exact"
    assert lot.first_reg_year == 2015
    assert lot.first_reg_month == 6
    assert lot.first_reg_date_str == "06.2015"
    assert lot.is_pass_corridor_3_5 is True
    assert lot.engine_cc == 1998
    assert lot.mileage_km == 88000
    assert lot.odometer_status == "confirmed"
    assert lot.transmission == "CVT"
    assert lot.drive_type == "4WD"
    assert lot.fuel_type == "gasoline"
    assert lot.color_ru == "Синий"
    assert lot.paint_code == "G1E"
    assert lot.overall_grade == "4"
    assert lot.exterior_grade == "3.5"
    assert lot.interior_grade == "B"
    assert lot.shaken_until == "2027-06"
    assert lot.recycling_fee_yen == 15000
    assert lot.recycling_fee_paid is True
    assert lot.equipment_ru == ["Климат-контроль", "Камера заднего вида"]
    assert lot.inspector_notes_raw == ["note raw"]
    assert lot.inspector_notes_ru == ["Заметка инспектора"]
    assert lot.seller_comments_ru == ["Комментарий продавца"]
    assert lot.extra_ru == ["Дополнительно"]
    assert lot.ocr_warnings == ["Blurred corner", "minor smudge"]
    assert lot.low_confidence_fields == ["trim"]
    # No bid price on the sheet: must remain unset for later resolution.
    assert lot.auction_bid_jpy is None

    flags = LotRiskFlags.objects.get(lot=lot)
    assert flags.is_flooded is True
    assert flags.underbody_rust is True
    assert flags.windshield_damage is True
    assert flags.airbag_deployed is False
    assert flags.repaired_grade_r_ra is False

    defects = list(LotDefect.objects.filter(lot=lot).order_by("panel_id"))
    assert len(defects) == 2
    assert defects[0].panel_id == BodyPanel.FRONT_LEFT_FENDER
    assert defects[0].panel_ru == "Переднее левое крыло"
    assert defects[0].defect_types == ["A1"]
    assert defects[0].severity == 2
    assert defects[0].raw_code == "A1"
    assert defects[0].description_ru == "Царапина"
    assert defects[1].panel_id == BodyPanel.REAR_BUMPER
    assert defects[1].defect_types == ["B2", "W1"]

    # Cache is cleared after parse; a second parse re-fetches and re-applies.
    calls.clear()
    parser.parse(batch_item)
    assert len(calls) == 1
    assert LotDefect.objects.filter(lot=lot).count() == 2


@pytest.mark.django_db
def test_gatekeeper_returns_reason_for_rejected_not_sheet(batch_item) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_rejected_response_body())

    parser = MlServiceParser(client=_client(handler))
    rejection = parser.gatekeeper(batch_item)

    assert rejection is not None
    assert "аукционным листом" in rejection
    assert parser.fast_header(batch_item) is None


@pytest.mark.django_db
def test_parse_raises_for_missing_cached_response(batch_item) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_rejected_response_body())

    parser = MlServiceParser(client=_client(handler))
    with pytest.raises(MlServiceError, match="no sheet"):
        parser.parse(batch_item)


@pytest.mark.django_db
def test_unknown_panel_id_skips_defect_and_warns(batch_item) -> None:
    body = _ok_response_body(
        sheet=_sheet_payload(
            defects=[
                {
                    "panel_id": "mystery_panel_zone",
                    "panel_ru": "Неизвестная зона",
                    "defect_types": ["A1"],
                    "severity": 1,
                    "description_ru": "Загадочное повреждение",
                    "raw_code": "A1",
                },
                {
                    "panel_id": "hood",
                    "panel_ru": "Капот",
                    "defect_types": ["U2"],
                    "severity": 2,
                    "description_ru": "Вмятина на капоте",
                    "raw_code": "U2",
                },
            ],
        )
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    parser = MlServiceParser(client=_client(handler))
    assert parser.gatekeeper(batch_item) is None
    parser.parse(batch_item)

    lot = batch_item.lot
    lot.refresh_from_db()
    defects = list(LotDefect.objects.filter(lot=lot))
    assert len(defects) == 1
    assert defects[0].panel_id == BodyPanel.HOOD
    assert any("mystery_panel_zone" in warning for warning in lot.ocr_warnings)
    assert any("Unknown panel_id" in warning for warning in lot.ocr_warnings)


@pytest.mark.django_db
def test_unknown_choice_values_become_null_with_warnings(batch_item) -> None:
    body = _ok_response_body(
        sheet=_sheet_payload(
            fuel_type="unknown-garbage",
            odometer_status="reset-by-wizard",
            drive_type="6WD",
            frame_id_confidence="vibes",
            auction_house="SUPER_AUCTION",
        )
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    parser = MlServiceParser(client=_client(handler))
    assert parser.gatekeeper(batch_item) is None
    parser.parse(batch_item)

    lot = batch_item.lot
    lot.refresh_from_db()
    assert lot.fuel_type is None
    assert lot.odometer_status is None
    assert lot.drive_type is None
    assert lot.frame_id_confidence is None
    assert lot.auction_house is None
    for field in ("fuel_type", "odometer_status", "drive_type", "frame_id_confidence"):
        assert any(field in warning for warning in lot.ocr_warnings)


@pytest.mark.django_db
def test_parse_overwrites_stale_risk_flags_and_defects(batch_item) -> None:
    lot = batch_item.lot
    LotRiskFlags.objects.create(lot=lot, is_flooded=True, hail_damage=True)
    LotDefect.objects.create(
        lot=lot,
        panel_id=BodyPanel.ROOF,
        panel_ru="Крыша",
        defect_types=["XX"],
        severity=4,
        raw_code="XX",
        description_ru="Старое повреждение",
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_ok_response_body())

    parser = MlServiceParser(client=_client(handler))
    assert parser.gatekeeper(batch_item) is None
    parser.parse(batch_item)

    flags = LotRiskFlags.objects.get(lot=lot)
    assert flags.is_flooded is True
    assert flags.hail_damage is False
    defects = list(LotDefect.objects.filter(lot=lot))
    assert {defect.panel_id for defect in defects} == {
        BodyPanel.FRONT_LEFT_FENDER,
        BodyPanel.REAR_BUMPER,
    }


@pytest.mark.django_db
def test_gatekeeper_raises_for_missing_file(batch_item) -> None:
    batch_item.original_file = None
    parser = MlServiceParser(client=_client(lambda _request: httpx.Response(200, content=b"{}")))
    with pytest.raises(MlServiceError, match="no original file"):
        parser.gatekeeper(batch_item)


@pytest.mark.django_db
def test_fast_header_without_make_returns_none(batch_item) -> None:
    body = _ok_response_body(sheet=_sheet_payload(make=None, model=None))

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    parser = MlServiceParser(client=_client(handler))
    assert parser.gatekeeper(batch_item) is None
    assert parser.fast_header(batch_item) is None


@pytest.mark.django_db
def test_parser_reads_settings_when_no_overrides(batch_item, settings) -> None:
    settings.ML_SERVICE_URL = "http://ml-settings.test"
    settings.ML_SERVICE_TIMEOUT_SEC = 12.5
    settings.ML_SERVICE_API_KEY = "settings-key"
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["api_key"] = request.headers.get("X-API-Key")
        return httpx.Response(200, content=_ok_response_body())

    captured: dict = {}
    real_client = MlServiceClient

    def spy_client(**kwargs: object) -> object:
        captured.update(kwargs)
        return real_client(transport=_transport(handler), **kwargs)  # type: ignore[arg-type]

    with patch("apps.lots.integrations.ml.parser.MlServiceClient", side_effect=spy_client):
        parser = MlServiceParser()
        assert parser.gatekeeper(batch_item) is None

    assert captured["base_url"] == "http://ml-settings.test"
    assert captured["timeout_sec"] == 12.5
    assert captured["api_key"] == "settings-key"
    assert seen["api_key"] == "settings-key"


@pytest.mark.django_db
def test_settings_module_exports_ml_service_config() -> None:
    """Django settings must expose the ML service config for the parser.

    parser.py reads django.conf.settings; the values are re-exported in
    config/settings/base.py. This test fails when the export is missing
    (the pytest-django settings fixture cannot catch it).
    """
    from django.conf import settings as django_settings

    assert hasattr(django_settings, "ML_SERVICE_URL")
    assert hasattr(django_settings, "ML_SERVICE_TIMEOUT_SEC")
    assert hasattr(django_settings, "ML_SERVICE_API_KEY")


@pytest.mark.django_db
def test_unknown_panel_defects_are_preserved_in_extra_ru(batch_item) -> None:
    """Defects outside the 16 canonical panels survive as Russian notes.

    ML reports structural entries (radiator core support, frame parts) as
    panel_id="other"; the raw observation must reach the lot's extra_ru
    instead of being dropped, alongside the ocr_warning.
    """
    lot = batch_item.lot

    def handler(_request: httpx.Request) -> httpx.Response:
        body = _ok_response_body(
            sheet=_sheet_payload(
                defects=[
                    {
                        "panel_id": "other",
                        "panel_ru": "рамка радиатора",
                        "defect_types": ["R"],
                        "severity": None,
                        "description_ru": "следы ремонта",
                        "raw_code": "R",
                    },
                    {
                        "panel_id": "hood",
                        "panel_ru": "Капот",
                        "defect_types": ["A1"],
                        "severity": 1,
                        "description_ru": "Царапина",
                        "raw_code": "A1",
                    },
                ],
            )
        )

        return httpx.Response(200, content=body)

    parser = MlServiceParser(client=_client(handler))
    assert parser.gatekeeper(batch_item) is None
    parser.parse(batch_item)

    lot.refresh_from_db()
    defects = list(LotDefect.objects.filter(lot=lot))
    assert [defect.panel_id for defect in defects] == [BodyPanel.HOOD]
    assert any("рамка радиатора" in note for note in lot.extra_ru)
    assert any("R" in note for note in lot.extra_ru)
    assert any("Unknown panel_id" in warning for warning in lot.ocr_warnings)
