"""Tests for recalculation edge cases, batch 429 rate limits, domain errors, and migrations."""

from __future__ import annotations

import importlib
import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from django.apps import apps
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from tests.test_lots_api import _make_png_bytes, _register_and_auth

from apps.lots.calculator.recalc import execute_recalculate, execute_reset_simulation
from apps.lots.exceptions import LotNotFoundDomainError, RecalcDomainError
from apps.lots.lifecycle import delete_lot, update_lot_archive_state
from apps.lots.models import CustomsCalculation, Lot

if TYPE_CHECKING:
    from django.test import Client


class _FakeRateRedis:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    def eval(self, _script: str, _numkeys: int, key: str, *_args) -> int:
        next_val = self.counters.get(key, 0) + 1
        self.counters[key] = next_val
        return next_val


@pytest.mark.django_db
def test_recalculate_omitting_include_repairs_preserves_persisted_false(
    api_client: Client,
) -> None:
    headers, user_id = _register_and_auth(api_client, "keep-repairs@example.com")
    lot = Lot.objects.get(user_id=user_id, frame_id="GB5-3179736")

    first = api_client.post(
        f"/api/v1/lots/{lot.id}/recalculate",
        {"bid_jpy": 1_040_000, "include_repairs": False},
        content_type="application/json",
        **headers,
    )
    assert first.status_code == 200
    assert first.json()["include_repairs"] is False
    turnkey_without_repairs = first.json()["turnkey_cost_rub"]

    # Second call omits include_repairs -> must keep False instead of resetting to True.
    second = api_client.post(
        f"/api/v1/lots/{lot.id}/recalculate",
        {"bid_jpy": 1_040_000},
        content_type="application/json",
        **headers,
    )
    assert second.status_code == 200
    assert second.json()["include_repairs"] is False
    assert second.json()["turnkey_cost_rub"] == turnkey_without_repairs
    lot.refresh_from_db()
    assert lot.is_repairs_included is False


@pytest.mark.django_db
def test_recalculate_rejects_custom_freight_above_50m_with_422(api_client: Client) -> None:
    headers, user_id = _register_and_auth(api_client, "max-freight@example.com")
    lot = Lot.objects.get(user_id=user_id, frame_id="RV3-1005521")

    too_high = api_client.post(
        f"/api/v1/lots/{lot.id}/recalculate",
        {"bid_jpy": 1_000_000, "custom_freight_rub": 50_000_001},
        content_type="application/json",
        **headers,
    )
    assert too_high.status_code == 422
    assert too_high.headers["Content-Type"].startswith("application/problem+json")

    ok_max = api_client.post(
        f"/api/v1/lots/{lot.id}/recalculate",
        {"bid_jpy": 1_000_000, "custom_freight_rub": 50_000_000},
        content_type="application/json",
        **headers,
    )
    assert ok_max.status_code == 200
    assert ok_max.json()["customs"]["freight_vladivostok_rub"] == 50_000_000


@pytest.mark.django_db
@override_settings(RATE_LIMIT_ENABLED=True)
def test_batch_upload_and_append_enforce_429_rate_limit(
    api_client: Client,
    monkeypatch,
) -> None:
    headers, _ = _register_and_auth(api_client, "batch-rl@example.com")
    fake_redis = _FakeRateRedis()
    monkeypatch.setattr("apps.core.redis_utils.get_redis_client", lambda: fake_redis)
    png_bytes = _make_png_bytes((128, 128), mode="RGB")

    batch_id = None
    with patch("apps.lots.pipeline.batches._schedule_batch_pipeline"):
        for idx in range(20):
            upload = SimpleUploadedFile(f"s{idx}.png", png_bytes, content_type="image/png")
            if idx == 0:
                resp = api_client.post("/api/v1/lots/batches", {"files": [upload]}, **headers)
                assert resp.status_code == 202
                batch_id = resp.json()["batch_id"]
            elif idx < 10:
                resp = api_client.post(
                    f"/api/v1/lots/batches/{batch_id}/items",
                    {"files": [upload]},
                    **headers,
                )
                assert resp.status_code == 202
            else:
                resp = api_client.post("/api/v1/lots/batches", {"files": [upload]}, **headers)
                assert resp.status_code == 202

        blocked_create = api_client.post(
            "/api/v1/lots/batches",
            {"files": [SimpleUploadedFile("over.png", png_bytes, content_type="image/png")]},
            **headers,
        )
        assert blocked_create.status_code == 429
        assert blocked_create.headers["Content-Type"].startswith("application/problem+json")

        blocked_append = api_client.post(
            f"/api/v1/lots/batches/{batch_id}/items",
            {"files": [SimpleUploadedFile("over2.png", png_bytes, content_type="image/png")]},
            **headers,
        )
        assert blocked_append.status_code == 429
        assert blocked_append.headers["Content-Type"].startswith("application/problem+json")


@pytest.mark.django_db
def test_domain_exceptions_are_http_free_and_translated_in_api(
    api_client: Client,
    user_factory,
) -> None:
    user = user_factory(email="domain-exc@example.com")
    missing_id = uuid.uuid4()

    with pytest.raises(LotNotFoundDomainError):
        execute_recalculate(user, missing_id, bid_jpy=500_000)
    with pytest.raises(LotNotFoundDomainError):
        execute_reset_simulation(user, missing_id)
    with pytest.raises(LotNotFoundDomainError):
        update_lot_archive_state(user, missing_id, is_archived=True)
    with pytest.raises(LotNotFoundDomainError):
        delete_lot(user, missing_id)

    from django.utils import timezone

    bare_lot = Lot.objects.create(user=user, completed_at=timezone.now(), make="Honda", model="Fit")
    with pytest.raises(RecalcDomainError):
        execute_reset_simulation(user, bare_lot.id)
    with pytest.raises(RecalcDomainError):
        execute_recalculate(user, bare_lot.id, bid_rub=500_000)

    # HTTP endpoints translate those domain errors to RFC 7807 404 / 400 ProblemDetail.
    headers, auth_uid = _register_and_auth(api_client, "api-exc@example.com")
    incomplete_calc_lot = Lot.objects.create(
        user_id=auth_uid,
        completed_at=timezone.now(),
        make="Honda",
        model="Fit",
    )
    assert (
        api_client.post(
            f"/api/v1/lots/{incomplete_calc_lot.id}/recalculate/reset",
            **headers,
        ).status_code
        == 400
    )
    assert api_client.delete(f"/api/v1/lots/{uuid.uuid4()}", **headers).status_code == 404
    assert (
        api_client.patch(
            f"/api/v1/lots/{uuid.uuid4()}",
            {"is_archived": True},
            content_type="application/json",
            **headers,
        ).status_code
        == 404
    )
    assert CustomsCalculation.objects.filter(lot=incomplete_calc_lot).exists() is False


@pytest.mark.django_db
def test_migration_0010_and_0006_independence(user_factory) -> None:
    user = user_factory(email="mig0010@example.com")
    legacy_lot = Lot.objects.create(user=user, bid_slider_min_jpy=300_000)
    custom_lot = Lot.objects.create(user=user, bid_slider_min_jpy=150_000)

    mig_0010 = importlib.import_module("apps.lots.migrations.0010_backfill_bid_slider_min_jpy")
    mig_0010.backfill_bid_slider_min_jpy(apps, None)

    legacy_lot.refresh_from_db()
    custom_lot.refresh_from_db()
    assert legacy_lot.bid_slider_min_jpy == 100_000
    assert custom_lot.bid_slider_min_jpy == 150_000

    mig_0006_path = (
        Path(__file__).resolve().parents[1]
        / "apps"
        / "lots"
        / "migrations"
        / "0006_lot_baseline_economics.py"
    )
    assert "starter_lots" not in mig_0006_path.read_text(encoding="utf-8")
