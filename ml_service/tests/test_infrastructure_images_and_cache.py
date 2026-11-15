"""Tests for image_formats, image_loader (SSRF + streaming), cropper, key_pool, and result_cache."""

import socket
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from ml_service.factories.sheet_factory import SheetFactory
from ml_service.infrastructure.image_cropper import PillowImageCropper, normalize_size
from ml_service.infrastructure.image_formats import detect_mime_from_magic_bytes
from ml_service.infrastructure.image_loader import AsyncImageLoader, validate_url_not_ssrf
from ml_service.infrastructure.key_pool import GeminiKeyPool
from ml_service.infrastructure.result_cache import ResultCache
from tests.conftest import make_image_bytes, make_raw_extraction


def test_detect_mime_from_magic_bytes() -> None:
    assert detect_mime_from_magic_bytes(make_image_bytes(fmt="JPEG")) == "image/jpeg"
    assert detect_mime_from_magic_bytes(make_image_bytes(fmt="WEBP")) == "image/webp"
    assert detect_mime_from_magic_bytes(make_image_bytes(fmt="HEIF")) == "image/heic"
    assert detect_mime_from_magic_bytes(make_image_bytes(fmt="PNG")) == "image/png"


@pytest.mark.asyncio
async def test_image_loader_from_bytes_formats_and_errors(sample_png_bytes: bytes) -> None:
    async with httpx.AsyncClient() as client:
        loader = AsyncImageLoader(http_client=client, max_bytes=1024 * 1024)

        png = await loader.load_from_bytes(sample_png_bytes, " sheet.png ")
        assert png.mime_type == "image/png"
        assert png.original_filename == "sheet.png"
        assert len(png.sha256) == 64

        heic = await loader.load_from_bytes(make_image_bytes(fmt="HEIF"), "photo.heic")
        assert heic.mime_type == "image/heic"

        with pytest.raises(ValueError, match="empty"):
            await loader.load_from_bytes(b"", "empty.png")

        with pytest.raises(ValueError, match="Invalid or corrupted"):
            await loader.load_from_bytes(b"not-an-image", "bad.png")

        small_loader = AsyncImageLoader(http_client=client, max_bytes=10)
        with pytest.raises(ValueError, match="exceeds maximum allowed"):
            await small_loader.load_from_bytes(sample_png_bytes, "big.png")

        gif_bytes = Image.new("RGB", (4, 4), (1, 2, 3))
        gif_buf = BytesIO()
        gif_bytes.save(gif_buf, format="GIF")
        with pytest.raises(ValueError, match="Unsupported image format"):
            await loader.load_from_bytes(gif_buf.getvalue(), "anim.gif")


@pytest.mark.asyncio
async def test_validate_url_not_ssrf() -> None:
    with pytest.raises(ValueError, match="Expected http or https"):
        await validate_url_not_ssrf("file:///etc/passwd")

    with pytest.raises(ValueError, match="Blocked unsafe hostname"):
        await validate_url_not_ssrf("http://localhost:8000/a.png")

    with pytest.raises(ValueError, match="Blocked unsafe hostname"):
        await validate_url_not_ssrf("https://metadata.internal/latest")

    with pytest.raises(ValueError, match="Blocked unsafe IP"):
        await validate_url_not_ssrf("http://127.0.0.1/a.png")

    with pytest.raises(ValueError, match="Blocked unsafe IP"):
        await validate_url_not_ssrf(
            "https://example.com/a.png",
            dns_resolver=lambda _host: ["10.0.0.5"],
        )

    with pytest.raises(ValueError, match="No IP addresses resolved"):
        await validate_url_not_ssrf(
            "https://example.com/a.png",
            dns_resolver=lambda _host: [],
        )

    await validate_url_not_ssrf(
        "https://cdn.example.com/sheet.png",
        dns_resolver=lambda _host: ["93.184.216.34"],
    )


@pytest.mark.asyncio
async def test_validate_url_not_ssrf_edge_cases() -> None:
    for blocked_url in (
        "https://localhost./a.png",
        "http://100.64.0.1/a.png",
        "http://[::1]/a.png",
        "http://[fe80::1]/a.png",
        "http://[::ffff:127.0.0.1]/a.png",
    ):
        with pytest.raises(ValueError, match="Blocked unsafe"):
            await validate_url_not_ssrf(blocked_url)

    def _raise_gai(_host: str) -> list[str]:
        raise socket.gaierror("DNS lookup failed")

    with pytest.raises(ValueError, match="Failed to resolve remote host"):
        await validate_url_not_ssrf("https://nonexistent.invalid/a.png", dns_resolver=_raise_gai)


@pytest.mark.asyncio
async def test_image_loader_from_url_redirects_and_limits(sample_jpeg_bytes: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/redirect-ok":
            return httpx.Response(302, headers={"location": "/final.jpg"})
        if path == "/redirect-ssrf":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/secret.jpg"})
        if path == "/redirect-loop":
            return httpx.Response(302, headers={"location": "/redirect-loop"})
        if path == "/redirect-no-location":
            return httpx.Response(302)
        if path == "/too-large-header":
            return httpx.Response(200, headers={"content-length": "99999999"}, content=b"x")
        if path == "/chunked-overflow":
            big_payload = sample_jpeg_bytes + (b"\x00" * (600 * 1024))
            return httpx.Response(200, stream=httpx.ByteStream(big_payload))
        if path == "/final.jpg":
            return httpx.Response(200, content=sample_jpeg_bytes)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        loader = AsyncImageLoader(
            http_client=client,
            max_bytes=512 * 1024,
            dns_resolver=lambda _host: ["93.184.216.34"],
        )

        loaded = await loader.load_from_url("https://cdn.example.com/redirect-ok")
        assert loaded.mime_type == "image/jpeg"
        assert loaded.original_filename == "final.jpg"

        with pytest.raises(ValueError, match="Blocked unsafe IP"):
            await loader.load_from_url("https://cdn.example.com/redirect-ssrf")

        with pytest.raises(ValueError, match="Too many redirects"):
            await loader.load_from_url("https://cdn.example.com/redirect-loop")

        with pytest.raises(ValueError, match="exceeds maximum allowed"):
            await loader.load_from_url("https://cdn.example.com/too-large-header")

        with pytest.raises(ValueError, match="Redirect response is missing Location header"):
            await loader.load_from_url("https://cdn.example.com/redirect-no-location")

        with pytest.raises(ValueError, match="exceeded maximum allowed"):
            await loader.load_from_url("https://cdn.example.com/chunked-overflow")

        with pytest.raises(httpx.HTTPStatusError):
            await loader.load_from_url("https://cdn.example.com/missing.jpg")


@pytest.mark.asyncio
async def test_pillow_image_cropper_produces_normalized_quadrants() -> None:
    cropper = PillowImageCropper(min_px=400, max_px=800, image_format="JPG", quality=85)
    assert cropper.image_format == "JPEG"
    assert cropper.mime_type == "image/jpeg"

    raw = make_image_bytes(fmt="PNG", size=(1000, 600))
    sliced = await cropper.slice_image_bytes(raw)
    assert set(sliced.crops_png) == {"top_left", "top_right", "bottom_left", "bottom_right"}
    assert 400 <= max(sliced.width, sliced.height) <= 800
    assert detect_mime_from_magic_bytes(sliced.full_png) == "image/jpeg"

    with Image.open(BytesIO(sliced.crops_png["top_left"])) as crop_img:
        assert 400 <= max(crop_img.size) <= 800

    with pytest.raises(ValueError, match="empty"):
        await cropper.slice_image_bytes(b"")

    with pytest.raises(ValueError, match="Unable to decode"):
        await cropper.slice_image_bytes(b"corrupted")

    with pytest.raises(ValueError, match="Unsupported crop image format"):
        PillowImageCropper(image_format="BMP")

    zero_img = Image.new("RGB", (10, 10))
    assert normalize_size(zero_img, min_px=100, max_px=200).size == (100, 100)


def test_gemini_key_pool_rotation_and_cooldown() -> None:
    with pytest.raises(ValueError, match="rpm_limit"):
        GeminiKeyPool(["k1"], rpm_limit=0)

    empty = GeminiKeyPool(["   "])
    assert empty.key_count == 0
    with pytest.raises(RuntimeError, match="No Gemini API keys"):
        empty.next_key()

    pool = GeminiKeyPool(["k1", "k2", "k3"], rpm_limit=2)
    assert pool.key_count == 3
    assert [pool.next_key(), pool.next_key(), pool.next_key()] == ["k1", "k2", "k3"]

    pool.mark_key_rate_limited("k1", cooldown_seconds=60.0)
    assert pool.next_key() == "k2"
    assert pool.next_key() == "k3"
    assert pool.next_key() == "k2"

    pool.mark_key_rate_limited("k2", cooldown_seconds=120.0)
    pool.mark_key_rate_limited("k3", cooldown_seconds=10.0)
    assert pool.next_key() == "k3"


@pytest.mark.asyncio
async def test_result_cache_memory_disk_and_corruption(tmp_path: Path) -> None:
    cache_dir = tmp_path / "sheets_cache"
    cache = ResultCache(cache_dir=cache_dir)
    factory = SheetFactory()
    entity = factory.build_result(
        make_raw_extraction(),
        processing_ms=100,
        mode_used="clean_digital",
        cached=False,
        model_used="gemini-3.6-flash",
        sha256="abcdef123456",
    )

    await cache.set("abcdef123456", entity)
    mem_hit = await cache.get("abcdef123456")
    assert mem_hit is not None
    assert mem_hit.meta.cached is True
    assert mem_hit.sheet is not None
    assert mem_hit.sheet.frame_id == "ZWE211-6012345"

    fresh_cache = ResultCache(cache_dir=cache_dir)
    disk_hit = await fresh_cache.get("abcdef123456")
    assert disk_hit is not None
    assert disk_hit.meta.cached is True
    assert disk_hit.sheet == mem_hit.sheet

    # Unsafe keys must not touch filesystem
    assert await fresh_cache.get("../evil") is None

    # Corrupted disk JSON should degrade gracefully to cache miss
    bad_path = cache_dir / "deadbeef.json"
    bad_path.write_text("{corrupt-json", encoding="utf-8")
    assert await fresh_cache.get("deadbeef") is None


@pytest.mark.asyncio
async def test_result_cache_lru_memory_eviction_preserves_disk(tmp_path: Path) -> None:
    cache_dir = tmp_path / "lru_cache"
    cache = ResultCache(cache_dir=cache_dir, max_memory_entries=2)
    factory = SheetFactory()

    for sha in ("key1", "key2", "key3"):
        entity = factory.build_result(
            make_raw_extraction(),
            processing_ms=50,
            mode_used="clean_digital",
            cached=False,
            model_used="gemini-3.6-flash",
            sha256=sha,
        )
        await cache.set(sha, entity)

    assert list(cache._memory.keys()) == ["key2", "key3"]
    # key1 was evicted from memory, yet remains recoverable from disk
    disk_recovered = await cache.get("key1")
    assert disk_recovered is not None
    assert disk_recovered.meta.cached is True
    assert list(cache._memory.keys()) == ["key3", "key1"]
