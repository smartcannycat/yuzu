import pytest
from pydantic import ValidationError

from config.settings.base import _build_database_config
from config.settings.config import AppSettings


def test_app_settings_parses_json_and_csv_lists() -> None:
    settings_json = AppSettings(
        _env_file=None,
        ALLOWED_HOSTS='["api.yuzu.ru", "localhost"]',
        CORS_ALLOWED_ORIGINS="https://yuzu.ru, https://app.yuzu.ru",
    )
    assert settings_json.ALLOWED_HOSTS == ["api.yuzu.ru", "localhost"]
    assert settings_json.CORS_ALLOWED_ORIGINS == ["https://yuzu.ru", "https://app.yuzu.ru"]


def test_production_settings_reject_insecure_defaults() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        AppSettings(
            _env_file=None,
            ENVIRONMENT="production",
            DEBUG=False,
            SECRET_KEY="django-insecure-short",
            ALLOWED_HOSTS=["api.yuzu.ru"],
        )

    with pytest.raises(ValidationError, match="ALLOWED_HOSTS"):
        AppSettings(
            _env_file=None,
            ENVIRONMENT="production",
            DEBUG=False,
            SECRET_KEY="x" * 40,
            ALLOWED_HOSTS=["*"],
        )

    valid_prod = AppSettings(
        _env_file=None,
        ENVIRONMENT="production",
        DEBUG=False,
        SECRET_KEY="x" * 40,
        ALLOWED_HOSTS=["api.yuzu.ru"],
    )
    assert valid_prod.is_production is True


def test_database_url_overrides_postgres_settings() -> None:
    settings_obj = AppSettings(
        _env_file=None,
        DATABASE_URL="postgresql://yuzu_user:s%40cret@db.internal:5433/yuzu_prod",
    )
    db_config = _build_database_config(settings_obj)
    assert db_config["ENGINE"] == "django.db.backends.postgresql"
    assert db_config["NAME"] == "yuzu_prod"
    assert db_config["USER"] == "yuzu_user"
    assert db_config["PASSWORD"] == "s@cret"
    assert db_config["HOST"] == "db.internal"
    assert db_config["PORT"] == 5433
    assert db_config["CONN_HEALTH_CHECKS"] is True
