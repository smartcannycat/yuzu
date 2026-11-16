"""Contract and integration tests for FastAPI endpoints, auth, rate limiting, and RFC 7807."""

import asyncio
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from google.genai.errors import ServerError

from ml_service.api import dependencies as api_deps
from ml_service.domains.entities import ChassisOcrEntity
from ml_service.domains.enums import BatchStatus, ParseStatus
from ml_service.factories.sheet_factory import SheetFactory
from ml_service.main import create_app
from ml_service.services.batch_parser_service import BatchCapacityError, BatchParserService
from tests.conftest import make_image_bytes, make_raw_extraction, make_settings


class _StubParserService:
    def __init__(self, *, mode: str = "ok") -> None:
        self.mode = mode
        self.factory = SheetFactory()

    async def parse_bytes(
        self,
        data: bytes,
        filename: str = "upload.png",
        *,
        force_refresh: bool = False,
        on_step=None,
        on_preview=None,
    ):
        if self.mode == "value_error":
            raise ValueError("Invalid or corrupted image bytes.")
        if self.mode == "timeout":
            raise TimeoutError("Deadline exceeded")
        if self.mode == "http_error":
            raise httpx.ConnectError("upstream failed")
        if self.mode == "rejected":
            return self.factory.build_rejected(
                processing_ms=20, sha256="rej", model_used="gemini-decision-1"
            )
        return self.factory.build_result(
            make_raw_extraction(),
            processing_ms=50,
            mode_used="clean_digital",
            cached=False,
            model_used="gemini-3.6-flash",
            sha256="abc123",
        )

    async def parse_url(self, url: str, *, force_refresh: bool = False):
        if self.mode == "http_error":
            raise httpx.ConnectError("upstream failed")
        if self.mode == "value_error":
            raise ValueError("Blocked unsafe IP address")
        if self.mode == "api_error":
            raise ServerError(503, {"error": {"message": "Gemini down"}})
        return await self.parse_bytes(b"url-bytes", force_refresh=force_refresh)


class _StubChassisClient:
    def __init__(self, *, fail_runtime: bool = False) -> None:
        self.fail_runtime = fail_runtime

    async def read_chassis_number(
        self, image_bytes: bytes, mime_type: str = "image/jpeg"
    ) -> ChassisOcrEntity:
        if self.fail_runtime:
            raise RuntimeError("No Gemini API keys configured in GeminiKeyPool.")
        return ChassisOcrEntity(frame_id="GB5-1025108", raw="GB5-1025108", confidence="high")


@pytest.mark.asyncio
async def test_auth_fail_closed_and_rate_limiting(tmp_path: Path) -> None:
    unconfigured_app = create_app(
        make_settings(
            tmp_path / "no_keys", ml_service_api_key_single="", ml_service_api_keys_raw=""
        )
    )
    async with (
        unconfigured_app.router.lifespan_context(unconfigured_app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=unconfigured_app),
            base_url="http://testserver",
        ) as client,
    ):
        resp = await client.get("/health")
        assert resp.status_code == 503
        assert resp.headers["content-type"].startswith("application/problem+json")

    limited_app = create_app(
        make_settings(
            tmp_path / "limited",
            ml_service_api_keys_raw="key-a,key-b",
            rate_limit_requests_per_minute=2,
        )
    )
    async with (
        limited_app.router.lifespan_context(limited_app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=limited_app),
            base_url="http://testserver",
        ) as client,
    ):
        unauth = await client.get("/health")
        assert unauth.status_code == 401
        assert unauth.headers["content-type"].startswith("application/problem+json")

        r1 = await client.get("/health", headers={"X-API-Key": "key-a"})
        r2 = await client.get("/health", headers={"X-API-Key": "key-b"})
        r3 = await client.get("/health", headers={"X-API-Key": "key-a"})
        assert r1.status_code == 200
        assert r1.json()["keys_configured"] == 2
        assert r2.status_code == 200
        assert r3.status_code == 429
        assert r3.headers["retry-after"] == "60"


@pytest.mark.asyncio
async def test_chassis_read_endpoint(tmp_path: Path, sample_jpeg_bytes: bytes) -> None:
    app = create_app(make_settings(tmp_path))
    headers = {"X-API-Key": "test-service-key"}

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client,
    ):
        app.state.chassis_ocr_client = _StubChassisClient()

        ok = await client.post(
            "/api/v1/chassis/read",
            headers=headers,
            files={"file": ("chassis.jpg", sample_jpeg_bytes, "image/jpeg")},
        )
        assert ok.status_code == 200
        assert ok.json() == {
            "frame_id": "GB5-1025108",
            "raw": "GB5-1025108",
            "confidence": "high",
            "cached": False,
        }

        bad_mime = await client.post(
            "/api/v1/chassis/read",
            headers=headers,
            files={"file": ("chassis.gif", b"GIF89a", "image/gif")},
        )
        assert bad_mime.status_code == 400

        spoofed_jpeg = await client.post(
            "/api/v1/chassis/read",
            headers=headers,
            files={"file": ("chassis.jpg", b"not-jpeg", "image/jpeg")},
        )
        assert spoofed_jpeg.status_code == 400

        empty_file = await client.post(
            "/api/v1/chassis/read",
            headers=headers,
            files={"file": ("empty.png", b"", "image/png")},
        )
        assert empty_file.status_code == 400

        app.state.chassis_ocr_client = _StubChassisClient(fail_runtime=True)
        unavailable = await client.post(
            "/api/v1/chassis/read",
            headers=headers,
            files={"file": ("chassis.jpg", sample_jpeg_bytes, "image/jpeg")},
        )
        assert unavailable.status_code == 503
        assert unavailable.headers["retry-after"] == "5"


@pytest.mark.asyncio
async def test_single_sheet_parse_and_parse_url_endpoints(
    tmp_path: Path, sample_png_bytes: bytes
) -> None:
    app = create_app(make_settings(tmp_path))
    headers = {"X-API-Key": "test-service-key"}

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client,
    ):
        app.state.parser_service = _StubParserService(mode="ok")
        ok = await client.post(
            "/api/v1/sheets/parse",
            headers=headers,
            files={"file": ("sheet.png", sample_png_bytes, "image/png")},
        )
        assert ok.status_code == 200
        body = ok.json()
        assert body["status"] == ParseStatus.OK.value
        assert body["sheet"]["frame_id"] == "ZWE211-6012345"

        bad_type = await client.post(
            "/api/v1/sheets/parse",
            headers=headers,
            files={"file": ("doc.pdf", b"%PDF", "application/pdf")},
        )
        assert bad_type.status_code == 400

        app.state.parser_service = _StubParserService(mode="timeout")
        timeout_resp = await client.post(
            "/api/v1/sheets/parse",
            headers=headers,
            files={"file": ("sheet.png", sample_png_bytes, "image/png")},
        )
        assert timeout_resp.status_code == 503

        app.state.parser_service = _StubParserService(mode="http_error")
        http_err_resp = await client.post(
            "/api/v1/sheets/parse",
            headers=headers,
            files={"file": ("sheet.png", sample_png_bytes, "image/png")},
        )
        assert http_err_resp.status_code == 503

        app.state.parser_service = _StubParserService(mode="rejected")
        rejected_resp = await client.post(
            "/api/v1/sheets/parse",
            headers=headers,
            files={"file": ("sheet.png", sample_png_bytes, "image/png")},
        )
        assert rejected_resp.status_code == 200
        assert rejected_resp.json()["status"] == ParseStatus.REJECTED_NOT_SHEET.value

        # /parse-url validation 422 -> RFC 7807 ProblemDetailsResponse
        invalid_body = await client.post(
            "/api/v1/sheets/parse-url",
            headers=headers,
            json={"url": "not-a-url", "unexpected": 1},
        )
        assert invalid_body.status_code == 422
        assert invalid_body.headers["content-type"].startswith("application/problem+json")
        assert len(invalid_body.json()["invalid_params"]) >= 1

        app.state.parser_service = _StubParserService(mode="http_error")
        bad_gw = await client.post(
            "/api/v1/sheets/parse-url",
            headers=headers,
            json={"url": "https://example.com/sheet.png"},
        )
        assert bad_gw.status_code == 502

        app.state.parser_service = _StubParserService(mode="value_error")
        ssrf_bad = await client.post(
            "/api/v1/sheets/parse-url",
            headers=headers,
            json={"url": "https://example.com/sheet.png"},
        )
        assert ssrf_bad.status_code == 400

        app.state.parser_service = _StubParserService(mode="api_error")
        gemini_down = await client.post(
            "/api/v1/sheets/parse-url",
            headers=headers,
            json={"url": "https://example.com/sheet.png"},
        )
        assert gemini_down.status_code == 503


@pytest.mark.asyncio
async def test_batch_endpoints_lifecycle_and_errors(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path, batch_max_items=2, batch_max_stored_batches=5))
    headers = {"X-API-Key": "test-service-key"}
    img = make_image_bytes(fmt="PNG", size=(120, 90))

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client,
    ):
        app.state.batch_service = BatchParserService(
            parser_service=_StubParserService(mode="ok"),
            max_items_per_batch=2,
            max_concurrency=2,
        )

        created = await client.post(
            "/api/v1/lots/batches",
            headers=headers,
            files=[("files", ("s1.png", img, "image/png"))],
        )
        assert created.status_code == 202
        batch_id = created.json()["batch_id"]

        # Poll until terminal
        progress_json = None
        for _ in range(50):
            poll = await client.get(f"/api/v1/lots/batches/{batch_id}", headers=headers)
            assert poll.status_code == 200
            progress_json = poll.json()
            if progress_json["status"] == BatchStatus.COMPLETED.value:
                break
            await asyncio.sleep(0.02)

        assert progress_json is not None
        assert progress_json["status"] == BatchStatus.COMPLETED.value
        assert progress_json["mascot"]["mood"] == "happy"
        assert progress_json["ready_count"] == 1
        assert progress_json["items"][0]["summary"]["frame_id"] == "ZWE211-6012345"

        # Adding items to a completed batch -> 409 Conflict
        conflict = await client.post(
            f"/api/v1/lots/batches/{batch_id}/items",
            headers=headers,
            files=[("files", ("s2.png", img, "image/png"))],
        )
        assert conflict.status_code == 409

        # Too many files -> 400
        too_many = await client.post(
            "/api/v1/lots/batches",
            headers=headers,
            files=[
                ("files", ("1.png", img, "image/png")),
                ("files", ("2.png", img, "image/png")),
                ("files", ("3.png", img, "image/png")),
            ],
        )
        assert too_many.status_code == 400

        # Unknown batch -> 404
        not_found = await client.get(f"/api/v1/lots/batches/{uuid4()}", headers=headers)
        assert not_found.status_code == 404

        # BatchCapacityError -> 429
        class _FullBatchService:
            async def create_batch(self, *_a, **_kw):
                raise BatchCapacityError("Queue full")

        app.state.batch_service = _FullBatchService()
        cap_resp = await client.post(
            "/api/v1/lots/batches",
            headers=headers,
            files=[("files", ("s1.png", img, "image/png"))],
        )
        assert cap_resp.status_code == 429
        assert cap_resp.headers["retry-after"] == "5"


@pytest.mark.asyncio
async def test_batch_add_items_active_202_and_unknown_404(tmp_path: Path) -> None:
    gate = asyncio.Event()

    class _HeldParserService(_StubParserService):
        async def parse_bytes(self, data: bytes, filename: str = "upload.png", **kwargs):
            await gate.wait()
            return await super().parse_bytes(data, filename, **kwargs)

    app = create_app(make_settings(tmp_path, batch_max_items=3, batch_max_stored_batches=5))
    headers = {"X-API-Key": "test-service-key"}
    img = make_image_bytes(fmt="PNG", size=(120, 90))

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client,
    ):
        app.state.batch_service = BatchParserService(
            parser_service=_HeldParserService(),
            max_items_per_batch=3,
            max_concurrency=2,
        )

        created = await client.post(
            "/api/v1/lots/batches",
            headers=headers,
            files=[("files", ("s1.png", img, "image/png"))],
        )
        assert created.status_code == 202
        batch_id = created.json()["batch_id"]

        added = await client.post(
            f"/api/v1/lots/batches/{batch_id}/items",
            headers=headers,
            files=[("files", ("s2.png", img, "image/png"))],
        )
        assert added.status_code == 202
        assert added.json()["total_count"] == 2

        missing = await client.post(
            f"/api/v1/lots/batches/{uuid4()}/items",
            headers=headers,
            files=[("files", ("s3.png", img, "image/png"))],
        )
        assert missing.status_code == 404

        gate.set()


@pytest.mark.asyncio
async def test_rate_limit_disabled_and_bucket_overflow_eviction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app(make_settings(tmp_path / "unlimited", rate_limit_requests_per_minute=0))
    headers = {"X-API-Key": "test-service-key"}
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client,
    ):
        for _ in range(5):
            resp = await client.get("/health", headers=headers)
            assert resp.status_code == 200

    # Bucket overflow eviction keeps buckets bounded under synthetic client hosts
    monkeypatch.setattr(api_deps, "_MAX_RATE_BUCKETS", 2)
    settings = make_settings(tmp_path / "evict", rate_limit_requests_per_minute=10)
    state = SimpleNamespace(
        _rate_limit_buckets={"10.0.0.1": deque([9e18]), "10.0.0.2": deque([9e18])}
    )
    fake_app = SimpleNamespace(state=state)
    fake_request = SimpleNamespace(app=fake_app, client=SimpleNamespace(host="10.0.0.3"))

    api_deps.rate_limit_dep(fake_request, settings)
    assert len(state._rate_limit_buckets) == 2
    assert "10.0.0.3" in state._rate_limit_buckets
