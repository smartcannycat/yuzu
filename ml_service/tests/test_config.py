"""Tests for ml_service configuration and key parsing."""

from pathlib import Path

from ml_service.config import Settings, _parse_key_list, get_settings


def test_parse_key_list_filters_placeholders_and_uses_fallback() -> None:
    assert _parse_key_list("your_api_key_1, change_me_2", "real-single-key") == ["real-single-key"]
    assert _parse_key_list("key-a, key-b, ", "ignored-single") == ["key-a", "key-b"]
    assert _parse_key_list("", "your_ml_service_api_key") == []


def test_settings_keys_and_fallback_models_dedup(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        ml_service_api_keys_raw="svc-1, svc-2",
        ml_service_api_key_single="svc-fallback",
        gemini_api_keys_raw="",
        gemini_api_key_single="gem-single",
        gemini_flash_model="gemini-3.6-flash",
        gemini_fallback_models_raw="gemini-3.6-flash, gemini-3.7-flash, gemini-3.7-flash, ",
        cache_dir=tmp_path / "rel_cache",
        max_image_size_mb=10,
    )

    assert settings.service_api_keys == ["svc-1", "svc-2"]
    assert settings.gemini_api_keys == ["gem-single"]
    assert settings.gemini_fallback_models == ["gemini-3.7-flash"]
    assert settings.max_image_bytes == 10 * 1024 * 1024
    assert settings.cache_dir.is_absolute()


def test_settings_resolves_relative_cache_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None, cache_dir=Path("custom/cache"))
    assert settings.cache_dir.is_absolute()
    assert settings.cache_dir.parts[-2:] == ("custom", "cache")


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second
