"""Security hardening and error-mapping tests (ML-SEC-01,03,04,06,07; ML-MAJ-04)."""

import asyncio
import importlib
from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import httpx
import pytest
from PIL import Image

from ml_service.infrastructure.image_cropper import PillowImageCropper
from ml_service.infrastructure.image_loader import (
    AsyncImageLoader,
    validate_url_not_ssrf,
    verify_image_mime,
)
from ml_service.main import create_app
from tests.conftest import make_image_bytes, make_settings


def _make_sparse_png_bytes(width: int, height: int) -> bytes:
    img = Image.new("1", (width, height), color=0)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_decompression_bomb_and_dimension_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    normal_png = make_image_bytes(fmt="PNG", size=(200, 120))

    # 1) Explicit side-length limit (> 12_000 px) in verify_image_mime and PillowImageCropper
    wide_png = _make_sparse_png_bytes(12001, 2)
    with pytest.raises(ValueError, match="exceed maximum side length"):
        verify_image_mime(wide_png)

    cropper = PillowImageCropper(min_px=400, max_px=800, image_format="JPEG")
    with pytest.raises(ValueError, match="exceed maximum side length"):
        await cropper.slice_image_bytes(wide_png)

    # 2) Image.DecompressionBombError is mapped to ValueError in both loader and cropper
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(ValueError, match="maximum allowed pixel count"):
        verify_image_mime(normal_png)
    with pytest.raises(ValueError, match="maximum allowed pixel count"):
        await cropper.slice_image_bytes(normal_png)
    monkeypatch.undo()

    # 3) /api/v1/chassis/read enforces stricter 25M px / 8000 px limits and offloads to thread
    app = create_app(make_settings(tmp_path))
    headers = {"X-API-Key": "test-service-key"}
    oversized_chassis_side = _make_sparse_png_bytes(8001, 2)
    oversized_chassis_pixels = _make_sparse_png_bytes(5001, 5001)

    called_in_thread: list[object] = []
    orig_to_thread = asyncio.to_thread

    async def _spy_to_thread(func, /, *args, **kwargs):
        called_in_thread.append(func)
        return await orig_to_thread(func, *args, **kwargs)

    api_router_mod = importlib.import_module("ml_service.api.router")
    monkeypatch.setattr(api_router_mod.asyncio, "to_thread", _spy_to_thread)

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client,
    ):
        resp_side = await client.post(
            "/api/v1/chassis/read",
            headers=headers,
            files={"file": ("chassis.png", oversized_chassis_side, "image/png")},
        )
        assert resp_side.status_code == 400
        assert resp_side.headers["content-type"].startswith("application/problem+json")

        resp_px = await client.post(
            "/api/v1/chassis/read",
            headers=headers,
            files={"file": ("chassis.png", oversized_chassis_pixels, "image/png")},
        )
        assert resp_px.status_code == 400
        assert verify_image_mime in called_in_thread


@pytest.mark.asyncio
async def test_docs_disabled_by_default_and_cors_restricted(tmp_path: Path) -> None:
    default_app = create_app(make_settings(tmp_path / "default"))
    headers = {"X-API-Key": "test-service-key", "Origin": "https://evil.example"}

    async with (
        default_app.router.lifespan_context(default_app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=default_app), base_url="http://testserver"
        ) as client,
    ):
        for path in ("/docs", "/redoc", "/openapi.json"):
            resp = await client.get(path, headers=headers)
            assert resp.status_code == 404
        health = await client.get("/health", headers=headers)
        assert health.status_code == 200
        assert "access-control-allow-origin" not in health.headers

    docs_app = create_app(
        make_settings(
            tmp_path / "docs_on",
            enable_docs=True,
            cors_allowed_origins=["https://admin.yuzu.local"],
        )
    )
    async with (
        docs_app.router.lifespan_context(docs_app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=docs_app), base_url="http://testserver"
        ) as client,
    ):
        openapi = await client.get("/openapi.json")
        assert openapi.status_code == 200
        allowed = await client.get(
            "/health",
            headers={"X-API-Key": "test-service-key", "Origin": "https://admin.yuzu.local"},
        )
        assert allowed.headers.get("access-control-allow-origin") == "https://admin.yuzu.local"
        blocked = await client.get(
            "/health",
            headers={"X-API-Key": "test-service-key", "Origin": "https://evil.example"},
        )
        assert "access-control-allow-origin" not in blocked.headers


@pytest.mark.asyncio
async def test_global_500_rfc7807_sanitized_422_and_pre_auth_rate_limit(
    tmp_path: Path, sample_png_bytes: bytes
) -> None:
    app = create_app(
        make_settings(
            tmp_path,
            pre_auth_rate_limit_requests_per_minute=3,
            rate_limit_requests_per_minute=10,
        )
    )
    headers = {"X-API-Key": "test-service-key"}

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://testserver",
        ) as client,
    ):
        # 1) Sanitized 422 does not leak raw input / exc.errors() dump into detail
        bad_req = await client.post(
            "/api/v1/sheets/parse-url",
            headers=headers,
            json={"url": "https://secret-user-input.invalid", "extra_secret": "do-not-leak"},
        )
        assert bad_req.status_code == 422
        assert bad_req.headers["content-type"].startswith("application/problem+json")
        assert bad_req.json()["detail"] == "Request validation failed."
        assert "do-not-leak" not in bad_req.json()["detail"]

        # 2) Global 500 returns RFC 7807 application/problem+json without exception internals
        class _BoomService:
            async def parse_bytes(self, *_a, **_kw):
                raise KeyError("super-secret-internal-key")

        app.state.parser_service = _BoomService()
        err_500 = await client.post(
            "/api/v1/sheets/parse",
            headers=headers,
            files={"file": ("sheet.png", sample_png_bytes, "image/png")},
        )
        assert err_500.status_code == 500
        assert err_500.headers["content-type"].startswith("application/problem+json")
        assert err_500.json()["detail"] == "Internal server error."
        assert "super-secret-internal-key" not in err_500.text

        # 3) Pre-auth IP rate limit blocks brute force BEFORE require_api_key_dep
        unauth1 = await client.get("/health", headers={"X-API-Key": "wrong-1"})
        assert unauth1.status_code == 401
        unauth_limited = await client.get("/health", headers={"X-API-Key": "wrong-2"})
        assert unauth_limited.status_code == 429
        assert unauth_limited.headers["retry-after"] == "60"


@pytest.mark.asyncio
async def test_parse_url_maps_gatekeeper_http_error_to_503_not_502(
    tmp_path: Path, sample_jpeg_bytes: bytes
) -> None:
    app = create_app(make_settings(tmp_path))
    headers = {"X-API-Key": "test-service-key"}

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client,
    ):
        parser_svc = app.state.parser_service
        parser_svc._image_loader = AsyncImageLoader(
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda _req: httpx.Response(200, content=sample_jpeg_bytes)
                ),
                trust_env=False,
            ),
            dns_resolver=lambda _h: ["93.184.216.34"],
        )

        class _GatekeeperHttpFailVision:
            flash_model_name = "gemini-3.6-flash"

            async def check_sheet(self, _full_png: bytes):
                raise httpx.ConnectError("gemini endpoint unreachable")

            async def extract_sheet(self, _sliced, _complexity):
                raise AssertionError("should not reach extract_sheet")

        parser_svc._vision_client = _GatekeeperHttpFailVision()
        resp = await client.post(
            "/api/v1/sheets/parse-url",
            headers=headers,
            json={"url": "https://cdn.example.com/sheet.jpg"},
        )
        assert resp.status_code == 503
        assert resp.headers["retry-after"] == "5"
        await parser_svc._image_loader.http_client.aclose()


@pytest.mark.asyncio
async def test_load_from_url_ssrf_pinning_site_local_userinfo_and_slow_drip(
    sample_jpeg_bytes: bytes,
) -> None:
    # 1) Block site-local IPv6 (fec0::1), userinfo credentials, and integer/octal/hex IPs
    for bad_url in (
        "http://[fec0::1]/sheet.jpg",
        "https://user:secret@cdn.example.com/sheet.jpg",
        "https://user@cdn.example.com/sheet.jpg",
        "http://2130706433/sheet.jpg",
        "http://0x7f000001/sheet.jpg",
        "http://0177.0.0.1/sheet.jpg",
        "https://cdn.example.com:badport/sheet.jpg",
        "https://cdn.example.com/\nsheet.jpg",
    ):
        with pytest.raises(ValueError):
            await validate_url_not_ssrf(bad_url)

    # 2) IP pinning preserves Host header and TLS sni_hostname
    seen_requests: list[httpx.Request] = []

    def _pin_handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(200, content=sample_jpeg_bytes)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_pin_handler), trust_env=False
    ) as client:
        loader = AsyncImageLoader(
            http_client=client,
            max_bytes=1024 * 1024,
            dns_resolver=lambda _host: ["93.184.216.34"],
        )
        assert loader.http_client.trust_env is False
        loaded = await loader.load_from_url("https://cdn.example.com:8443/path/sheet.jpg")
        assert loaded.original_filename == "sheet.jpg"
        assert len(seen_requests) == 1
        req = seen_requests[0]
        assert req.url.host == "93.184.216.34"
        assert req.url.port == 8443
        assert req.headers["host"] == "cdn.example.com:8443"
        assert req.extensions.get("sni_hostname") == "cdn.example.com"

    # 3) Slow-drip DoS aborted by asyncio.timeout
    class _SlowDripStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield sample_jpeg_bytes[:10]
            await asyncio.sleep(0.5)
            yield sample_jpeg_bytes[10:]

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _req: httpx.Response(200, stream=_SlowDripStream())),
        trust_env=False,
    ) as slow_client:
        slow_loader = AsyncImageLoader(
            http_client=slow_client,
            dns_resolver=lambda _host: ["93.184.216.34"],
            total_timeout_seconds=0.05,
        )
        with pytest.raises(TimeoutError):
            await slow_loader.load_from_url("https://cdn.example.com/slow.jpg")

    # 4) Default AsyncImageLoader constructs client with trust_env=False
    default_loader = AsyncImageLoader()
    assert default_loader.http_client.trust_env is False
    await default_loader.http_client.aclose()


def test_settings_default_jst_date_and_utc_rollover(tmp_path: Path) -> None:
    from ml_service.config import resolve_reference_date
    from ml_service.factories.normalizers import calculate_age_and_corridor, parse_japanese_date
    from ml_service.factories.sheet_factory import SheetFactory
    from tests.conftest import make_raw_extraction

    settings = make_settings(tmp_path)
    assert settings.reference_year is None
    assert settings.reference_month is None

    # 2026-12-31 16:00 UTC == 2027-01-01 01:00 Asia/Tokyo
    utc_dt = datetime(2026, 12, 31, 16, 0, tzinfo=ZoneInfo("UTC"))
    with patch(
        "ml_service.config.current_jst_datetime",
        return_value=utc_dt.astimezone(ZoneInfo("Asia/Tokyo")),
    ):
        assert resolve_reference_date(None, None) == (2027, 1)
        assert resolve_reference_date(2025, 4) == (2025, 4)
        assert parse_japanese_date("9.02")[0] == 2027
        age_str, in_corridor = calculate_age_and_corridor(2023, 1)
        assert age_str is not None and "4 года 0 мес." in age_str
        assert in_corridor is True
        res = SheetFactory().build_result(
            make_raw_extraction(first_reg_raw="2023年1月"),
            processing_ms=10,
            mode_used="clean_digital",
            cached=False,
            model_used="gemini-3.6-flash",
            sha256="jst123",
        )
        assert res.sheet is not None
        assert res.sheet.is_pass_corridor_3_5 is True


def test_settings_load_throughput_rate_limits_from_config_toml() -> None:
    from ml_service.config import Settings

    loaded = Settings()
    assert loaded.rate_limit_requests_per_minute == 600
    assert loaded.pre_auth_rate_limit_requests_per_minute == 1200
