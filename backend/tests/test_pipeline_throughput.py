"""Tests for pipeline concurrency, Aleado cache/OCR overlap, and scraper parallelism."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from pydantic import ValidationError
from redis.exceptions import RedisError

from apps.core.enums import BatchStatus, ItemProcessingStatus, TaskStep
from apps.integrations.aleado import AleadoClient, AleadoLotDetail, AleadoLotRow
from apps.integrations.aleado.cache import AleadoCache
from apps.integrations.aleado.service import AleadoCrossAuditService
from apps.integrations.drom.client import DromHttpClient
from apps.integrations.drom.schemas import DromSearchCriteria
from apps.integrations.drom.service import DromMarketService
from apps.integrations.farpost import cache as farpost_cache
from apps.integrations.farpost.client import PartCriteria, PartOffer
from apps.integrations.farpost.service import estimate_repair
from apps.integrations.ml.client import MlServiceClient
from apps.lots.models import Batch, BatchItem, Lot, LotDefect
from apps.lots.pipeline import run_batch_pipeline, stages
from apps.lots.pipeline.leases import batch_lock_key
from config.settings.config import AppSettings

_ALEADO_FIXTURES = Path(__file__).parent / "fixtures" / "aleado"


class _FakeRedis:
    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            return self.kv.get(key)

    def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> bool:
        with self._lock:
            if nx and key in self.kv:
                return False
            self.kv[key] = value
            if ex is not None:
                self.ttls[key] = ex
            return True

    def exists(self, key: str) -> int:
        with self._lock:
            return 1 if key in self.kv else 0

    def eval(self, script: str, _numkeys: int, key: str, *args):
        with self._lock:
            token = args[0]
            if self.kv.get(key) != token:
                return 0
            if "EXPIRE" in script:
                self.ttls[key] = int(args[1])
                return 1
            if "DEL" in script:
                del self.kv[key]
                self.ttls.pop(key, None)
                return 1
            return 0


def _jpeg_upload(name: str = "sheet.jpg") -> SimpleUploadedFile:
    buf = BytesIO()
    Image.new("RGB", (64, 64), (240, 240, 240)).save(buf, format="JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


def _search_html_with_ids(ids: list[str]) -> str:
    rows = []
    for index, internal_id in enumerate(ids, start=1):
        rows.append(
            f'<div id="priceLotS{index}" style="display:none">100</div>'
            f'<tr class="ColorGreed2" id="cell_{index}">'
            f'<td id="date_{index}">2025-11-10 00:00:00</td>'
            f'<td id="bid_number_{index}">'
            f'<a href="/auctions/?p=project/lot&amp;id={internal_id}"><b>{index}</b></a></td>'
            f'<td id="auction_{index}">USS Tokyo</td>'
            f'<td id="model_{index}">FREED</td>'
            f'<td id="grade_{index}">4</td>'
            f'<td id="year_{index}">2017</td>'
            f'<td id="mileage_{index}">{30000 + index * 1000}</td>'
            f'<td id="displacement_{index}">1500cc</td>'
            f'<td id="model_type_{index}">GB5</td>'
            f'<td id="result_{index}">sold</td>'
            f'<td id="scores_{index}">4</td></tr>'
        )
    return (
        "<html><body>Sign out"
        f'<div class="Header2">Found total lots: <b><font color="red">{len(ids)}</font></b>'
        + "".join(rows)
        + "</body></html>"
    )


def _ml_client_with_barrier(frame_id: str, barrier: threading.Barrier) -> MlServiceClient:
    payload = {
        "frame_id": frame_id,
        "raw": frame_id,
        "confidence": "high",
        "cached": False,
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        barrier.wait()
        return httpx.Response(200, json=payload)

    return MlServiceClient(
        base_url="http://ml.test",
        timeout_sec=5.0,
        transport=httpx.MockTransport(handler),
    )


def test_pipeline_config_and_step_delay_defaults(monkeypatch) -> None:
    defaults = AppSettings(_env_file=None)
    assert defaults.PIPELINE_BATCH_ITEM_CONCURRENCY == 4
    assert defaults.ALEADO_BUDGET_SEC == 25.0
    assert defaults.ALEADO_OCR_MAX_WORKERS == 3
    assert defaults.ALEADO_SEARCH_CACHE_TTL_SEC == 1800
    assert defaults.ALEADO_DETAIL_CACHE_TTL_SEC == 604800
    assert defaults.ALEADO_CHASSIS_CACHE_TTL_SEC == 2592000
    assert stages._PIPELINE_STEP_DELAY_SEC == 0.0

    monkeypatch.setenv("PIPELINE_BATCH_ITEM_CONCURRENCY", "6")
    assert AppSettings(_env_file=None).PIPELINE_BATCH_ITEM_CONCURRENCY == 6

    for field, invalid in (
        ("PIPELINE_BATCH_ITEM_CONCURRENCY", 0),
        ("ALEADO_BUDGET_SEC", 0),
        ("ALEADO_OCR_MAX_WORKERS", 99),
    ):
        with pytest.raises(ValidationError):
            AppSettings(_env_file=None, **{field: invalid})


@pytest.mark.django_db(transaction=True)
def test_run_batch_pipeline_processes_items_concurrently_and_isolates_item_crash(
    user_factory, settings
) -> None:
    settings.PIPELINE_BATCH_ITEM_CONCURRENCY = 2
    user = user_factory(email="concurrent-batch@example.com")
    batch = Batch.objects.create(user=user, status=BatchStatus.QUEUED)
    items = [
        BatchItem.objects.create(
            batch=batch,
            file_index=idx,
            original_filename=f"s{idx}.jpg",
            original_file=_jpeg_upload(f"s{idx}.jpg"),
            status=ItemProcessingStatus.QUEUED,
            current_step=TaskStep.GATEKEEPER,
        )
        for idx in range(3)
    ]

    barrier = threading.Barrier(2, timeout=5)
    fake_redis = _FakeRedis()

    def fake_process(claimed: BatchItem) -> None:
        if claimed.file_index in {0, 1}:
            barrier.wait()
            claimed.status = ItemProcessingStatus.READY
            claimed.current_step = TaskStep.COMPLETED
            claimed.save(update_fields=["status", "current_step", "updated_at"])
            return
        raise RuntimeError("isolated item boom")

    with (
        patch("apps.core.redis_utils.get_redis_client", return_value=fake_redis),
        patch("apps.lots.pipeline.runner._process_item", side_effect=fake_process),
    ):
        run_batch_pipeline(batch.id)

    batch.refresh_from_db()
    for item in items:
        item.refresh_from_db()
    assert items[0].status == ItemProcessingStatus.READY
    assert items[1].status == ItemProcessingStatus.READY
    assert items[2].status == ItemProcessingStatus.FAILED
    assert batch.status == BatchStatus.PARTIAL_FAILED
    assert batch_lock_key(batch.id) not in fake_redis.kv


@pytest.mark.django_db(transaction=True)
def test_run_batch_pipeline_picks_up_dynamically_appended_item(user_factory, settings) -> None:
    settings.PIPELINE_BATCH_ITEM_CONCURRENCY = 2
    user = user_factory(email="dynamic-append@example.com")
    batch = Batch.objects.create(user=user, status=BatchStatus.QUEUED)
    first = BatchItem.objects.create(
        batch=batch,
        file_index=0,
        original_filename="first.jpg",
        original_file=_jpeg_upload("first.jpg"),
        status=ItemProcessingStatus.QUEUED,
        current_step=TaskStep.GATEKEEPER,
    )
    appended_flag = threading.Event()
    fake_redis = _FakeRedis()

    def fake_process(claimed: BatchItem) -> None:
        if claimed.file_index == 0 and not appended_flag.is_set():
            appended_flag.set()
            BatchItem.objects.create(
                batch=batch,
                file_index=1,
                original_filename="appended.jpg",
                original_file=_jpeg_upload("appended.jpg"),
                status=ItemProcessingStatus.QUEUED,
                current_step=TaskStep.GATEKEEPER,
            )
        claimed.status = ItemProcessingStatus.READY
        claimed.current_step = TaskStep.COMPLETED
        claimed.save(update_fields=["status", "current_step", "updated_at"])

    with (
        patch("apps.core.redis_utils.get_redis_client", return_value=fake_redis),
        patch("apps.lots.pipeline.runner._process_item", side_effect=fake_process),
    ):
        run_batch_pipeline(batch.id)

    batch.refresh_from_db()
    first.refresh_from_db()
    appended = BatchItem.objects.get(batch=batch, file_index=1)
    assert first.status == ItemProcessingStatus.READY
    assert appended.status == ItemProcessingStatus.READY
    assert batch.status == BatchStatus.COMPLETED


def test_aleado_shared_session_single_flight_login_and_reauth() -> None:
    AleadoClient.clear_shared_sessions()
    lock = threading.Lock()
    login_count = 0
    active_token = "v1"

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal login_count
        url = str(request.url)
        if "p=auth/login" in url:
            return httpx.Response(200, text="<html>Login to Auctions system</html>")
        if "/auth/login.php" in url:
            time.sleep(0.03)
            with lock:
                login_count += 1
                token = active_token
            return httpx.Response(
                302,
                headers={
                    "Location": "/auctions/",
                    "Set-Cookie": f"sid={token}; Path=/",
                },
            )
        cookie_header = request.headers.get("cookie", "")
        if f"sid={active_token}" not in cookie_header:
            return httpx.Response(302, headers={"Location": "/?p=auth/login"})
        return httpx.Response(200, text=_search_html_with_ids([]))

    try:
        transport = httpx.MockTransport(handler)
        start_barrier = threading.Barrier(4, timeout=5)
        errors: list[BaseException] = []

        def worker() -> None:
            try:
                client = AleadoClient(
                    username="u",
                    password="p",
                    request_interval_sec=0.0,
                    transport=transport,
                    share_session=True,
                )
                start_barrier.wait()
                assert client.search_lots("GB5") == []
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert not errors
        assert login_count == 1

        fifth = AleadoClient(
            username="u",
            password="p",
            request_interval_sec=0.0,
            transport=transport,
            share_session=True,
        )
        assert fifth.search_lots("GB5") == []
        assert login_count == 1

        # Simulate cookie expiry on Aleado side -> 2 concurrent clients do single-flight re-login.
        c1 = AleadoClient(
            username="u",
            password="p",
            request_interval_sec=0.0,
            transport=transport,
            share_session=True,
        )
        c2 = AleadoClient(
            username="u",
            password="p",
            request_interval_sec=0.0,
            transport=transport,
            share_session=True,
        )
        active_token = "v2"
        reauth_barrier = threading.Barrier(2, timeout=5)

        def reauth_worker(c: AleadoClient) -> None:
            try:
                reauth_barrier.wait()
                assert c.search_lots("GB5") == []
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        t1 = threading.Thread(target=reauth_worker, args=(c1,))
        t2 = threading.Thread(target=reauth_worker, args=(c2,))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)
        assert not errors
        assert login_count == 2
    finally:
        AleadoClient.clear_shared_sessions()


@pytest.mark.django_db
def test_aleado_redis_cache_tiers_and_fail_open(user_factory) -> None:
    user = user_factory(email="aleado-cache@example.com")
    lot = Lot.objects.create(
        user=user,
        model_code="GB5",
        first_reg_year=2017,
        mileage_km=40000,
        overall_grade="4",
        lot_number="10034",
        frame_id="GB5-1025108",
    )
    fake_redis = _FakeRedis()
    cache = AleadoCache(redis_client=fake_redis)

    cached_rows = [
        AleadoLotRow(
            trading_date=datetime(2025, 11, 10),
            lot_number="201",
            auction_house="USS Tokyo",
            model_name="FREED",
            grade="4",
            year=2017,
            mileage_km=31000,
            displacement_cc=1500,
            transmission="IAT",
            color="WHITE",
            model_type="GB5",
            start_price_jpy=500000,
            result="sold",
            internal_id="c1",
            photo_url=None,
        ),
        AleadoLotRow(
            trading_date=datetime(2025, 10, 5),
            lot_number="202",
            auction_house="TAA Kanto",
            model_name="FREED",
            grade="4",
            year=2017,
            mileage_km=32000,
            displacement_cc=1500,
            transmission="IAT",
            color="RED",
            model_type="GB5",
            start_price_jpy=550000,
            result="sold",
            internal_id="c2",
            photo_url=None,
        ),
    ]
    cached_detail = AleadoLotDetail(
        scores="4",
        start_price_jpy=550000,
        mileage_km=32000,
        chassis_image_url="https://p3.aleado.com/chassis/c2.jpg",
        model_type="GB5",
        year=2017,
        auction_house="TAA Kanto",
        lot_number="202",
        trading_datetime=datetime(2025, 10, 5),
        result="sold",
        equipment=None,
        condition=None,
    )
    cache.set_search("GB5", 2017, cached_rows)
    cache.set_chassis("c1", "GB5-9999999")
    cache.set_chassis("c2", "GB5-1025108")
    cache.set_detail("c2", cached_detail)

    http_calls: list[str] = []
    ocr_calls = 0

    def aleado_handler(request: httpx.Request) -> httpx.Response:
        http_calls.append(str(request.url))
        return httpx.Response(200, text="Sign out")

    def ml_handler(_request: httpx.Request) -> httpx.Response:
        nonlocal ocr_calls
        ocr_calls += 1
        return httpx.Response(200, json={"frame_id": "GB5-1025108", "raw": "GB5-1025108"})

    service = AleadoCrossAuditService(
        client=AleadoClient(
            username="u", password="p", transport=httpx.MockTransport(aleado_handler)
        ),
        ml_client=MlServiceClient(
            base_url="http://ml.test",
            timeout_sec=5.0,
            transport=httpx.MockTransport(ml_handler),
        ),
        cache=cache,
    )
    outcome = service.audit_lot(lot)
    assert outcome.times_auctioned == 1
    assert http_calls == []
    assert ocr_calls == 0

    class _BrokenRedis:
        def get(self, _key: str):
            raise RedisError("redis down")

        def set(self, *_args, **_kwargs):
            raise RedisError("redis down")

    detail_html = (
        "<html><body>Sign out"
        + (_ALEADO_FIXTURES / "lot_detail_freed.html").read_text(encoding="utf-8")
        + "</body></html>"
    )

    def live_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "chassis" in url:
            return httpx.Response(200, content=b"img-bytes")
        if "p=project/lot" in url or "p=project%2Flot" in url:
            return httpx.Response(200, text=detail_html)
        return httpx.Response(200, text=_search_html_with_ids(["901"]))

    fail_open_service = AleadoCrossAuditService(
        client=AleadoClient(
            username="u", password="p", transport=httpx.MockTransport(live_handler)
        ),
        ml_client=_ml_client_with_barrier("GB5-1025108", threading.Barrier(1)),
        cache=AleadoCache(redis_client=_BrokenRedis()),
    )
    live_outcome = fail_open_service.audit_lot(lot)
    assert live_outcome.times_auctioned == 1


@pytest.mark.django_db
def test_aleado_verifier_overlaps_ocr_and_respects_budget(user_factory) -> None:
    user = user_factory(email="aleado-ocr-overlap@example.com")
    lot = Lot.objects.create(
        user=user,
        model_code="GB5",
        first_reg_year=2017,
        mileage_km=25000,
        overall_grade="4",
        lot_number="10034",
        frame_id="GB5-1025108",
    )
    detail_html = (
        "<html><body>Sign out"
        + (_ALEADO_FIXTURES / "lot_detail_freed.html").read_text(encoding="utf-8")
        + "</body></html>"
    )

    def overlap_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "chassis" in url:
            return httpx.Response(200, content=b"img-bytes")
        if "p=project/lot" in url or "p=project%2Flot" in url:
            return httpx.Response(200, text=detail_html)
        return httpx.Response(200, text=_search_html_with_ids(["101", "102"]))

    ocr_barrier = threading.Barrier(2, timeout=5)
    service = AleadoCrossAuditService(
        client=AleadoClient(
            username="u",
            password="p",
            request_interval_sec=0.0,
            transport=httpx.MockTransport(overlap_handler),
        ),
        ml_client=_ml_client_with_barrier("GB5-1025108", ocr_barrier),
        ocr_max_workers=2,
        budget_sec=10.0,
    )
    outcome = service.audit_lot(lot)
    assert outcome.times_auctioned == 2
    assert [row.lot_number for row in outcome.history] == ["1", "2"]

    # Budget exhaustion stops fetching candidate #2 after candidate #1 consumes the budget.
    fetched_ids: list[str] = []

    def budget_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "chassis" in url:
            time.sleep(0.06)
            return httpx.Response(200, content=b"img-bytes")
        if "p=project/lot" in url or "p=project%2Flot" in url:
            fetched_ids.append(url.split("id=")[-1].split("&")[0])
            return httpx.Response(200, text=detail_html)
        return httpx.Response(200, text=_search_html_with_ids(["201", "202"]))

    budget_service = AleadoCrossAuditService(
        client=AleadoClient(
            username="u",
            password="p",
            request_interval_sec=0.0,
            transport=httpx.MockTransport(budget_handler),
        ),
        ml_client=_ml_client_with_barrier("GB5-1025108", threading.Barrier(1)),
        budget_sec=0.04,
        ocr_max_workers=2,
    )
    budget_outcome = budget_service.audit_lot(lot)
    assert fetched_ids == ["201"]
    assert budget_outcome.times_auctioned == 1


def _make_drom_ssr_html(prices: list[int]) -> bytes:
    bulls = [
        {
            "bullId": idx,
            "price": price,
            "url": f"https://auto.drom.ru/vladivostok/toyota/corolla/{idx}.html",
            "title": "Toyota Corolla, 2020",
            "description": "",
            "sold": False,
            "carState": [],
            "location": "Владивосток",
            "attributes": [{"type": "plain", "payload": "1.2 л (116 л.с.)"}],
        }
        for idx, price in enumerate(prices, start=1)
    ]
    payload = {
        "__slug": "bulls-list-auto",
        "bullList": {"bullsData": [{"title": None, "bulls": bulls}]},
        "filter": {"filledParams": {}},
    }
    html = (
        "<!DOCTYPE html><html><head>"
        '<meta http-equiv="Content-Type" content="text/html; charset=windows-1251">'
        f"</head><body><script>{json.dumps(payload, ensure_ascii=False)}</script></body></html>"
    )
    return html.encode("cp1251")


@pytest.mark.django_db(transaction=True)
def test_drom_parallel_power_and_cascade_with_isolated_client() -> None:
    barrier = threading.Barrier(2, timeout=5)
    seen_clients: list[str] = []
    barrier_entered: set[str] = set()
    lock = threading.Lock()

    listings_bytes = _make_drom_ssr_html([1_400_000, 1_500_000, 1_600_000])
    catalog_model_html = (
        '<html><body><a href="/catalog/toyota/corolla/g_2019_1/">Corolla (NRE210W)</a>'
        "</body></html>"
    )
    catalog_gen_html = (
        "<html><body><table>"
        "<tr><td>1.2 л, 116 л.с., бензин, МКПП, передний привод</td>"
        "<td>Кузов: 3BA-NRE210W</td></tr>"
        "<tr><td>10.2019 - н.в.</td></tr>"
        "</table></body></html>"
    )

    def make_handler(role: str):
        def handler(request: httpx.Request) -> httpx.Response:
            with lock:
                seen_clients.append(role)
            url = str(request.url)
            if url.endswith("/catalog/toyota/corolla/"):
                if role == "power":
                    should_wait = False
                    with lock:
                        if "power" not in barrier_entered:
                            barrier_entered.add("power")
                            should_wait = True
                    if should_wait:
                        barrier.wait()
                return httpx.Response(200, text=catalog_model_html)
            if url.endswith("/catalog/toyota/corolla/g_2019_1/"):
                return httpx.Response(200, text=catalog_gen_html)
            if "auto.drom.ru" in url:
                if role == "main":
                    should_wait = False
                    with lock:
                        if "main" not in barrier_entered:
                            barrier_entered.add("main")
                            should_wait = True
                    if should_wait:
                        barrier.wait()
                return httpx.Response(
                    200,
                    headers={"Content-Type": "text/html; charset=windows-1251"},
                    content=listings_bytes,
                )
            return httpx.Response(404, text="")

        return handler

    service = DromMarketService(
        client=DromHttpClient(transport=httpx.MockTransport(make_handler("main"))),
        power_client_factory=lambda: DromHttpClient(
            transport=httpx.MockTransport(make_handler("power"))
        ),
    )
    criteria = DromSearchCriteria(
        make="Toyota",
        model="Corolla Touring",
        year=2020,
        engine_cc=1196,
        model_code="3BA-NRE210W",
    )
    result = service.evaluate(criteria)
    assert result.market_price_rf_rub == 1_500_000
    assert result.power_hp == 116
    assert "main" in seen_clients and "power" in seen_clients


@pytest.mark.django_db(transaction=True)
def test_farpost_parallel_replacement_panels_preserve_order(user_factory, monkeypatch) -> None:
    monkeypatch.setattr(farpost_cache, "_local_cooldown_until", 0.0)
    monkeypatch.setattr(farpost_cache, "get_redis_client", lambda: None)

    user = user_factory(email="farpost-parallel@example.com")
    lot = Lot.objects.create(
        user=user,
        make="Toyota",
        model="Corolla",
        model_code="NRE210",
        frame_id="NRE210-1234567",
        paint_code="040",
    )
    for panel_id, panel_ru in (
        ("tailgate", "Крышка багажника"),
        ("front_bumper", "Передний бампер"),
        ("hood", "Капот"),
    ):
        LotDefect.objects.create(
            lot=lot,
            panel_id=panel_id,
            panel_ru=panel_ru,
            defect_types=["X"],
            raw_code="X",
        )

    barrier = threading.Barrier(2, timeout=5)
    lock = threading.Lock()
    entered_concurrent = 0
    created_clients: list[object] = []
    entered_count = 0
    exited_count = 0

    class _IsolatedClient:
        def __enter__(self) -> _IsolatedClient:
            nonlocal entered_count
            with lock:
                entered_count += 1
            return self

        def __exit__(self, *_args: object) -> None:
            nonlocal exited_count
            with lock:
                exited_count += 1

        def search(
            self, criteria: PartCriteria, *, deadline: float | None = None
        ) -> list[PartOffer]:
            nonlocal entered_concurrent
            should_wait = False
            with lock:
                if entered_concurrent < 2:
                    entered_concurrent += 1
                    should_wait = True
            if should_wait:
                barrier.wait()
            return [
                PartOffer(
                    offer_id=criteria.panel_id,
                    url=f"https://www.farpost.ru/part/{criteria.panel_id}",
                    title=f"{criteria.part_name} Toyota NRE210 040",
                    price_rub=12000,
                    color_matched=True,
                )
            ]

    def make_client() -> _IsolatedClient:
        instance = _IsolatedClient()
        with lock:
            created_clients.append(instance)
        return instance

    result = estimate_repair(lot, client_factory=make_client)  # type: ignore[arg-type]
    assert [part.panel_id for part in result.parts] == ["front_bumper", "hood", "tailgate"]
    assert all(part.price_from_rub == 12000 for part in result.parts)
    assert result.total_parts_from_rub == 36000
    assert len(created_clients) == 3
    assert entered_count == 3
    assert exited_count == 3
