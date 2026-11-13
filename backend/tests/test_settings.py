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
        CBRF_FALLBACK_RATES='{"eur_rub": 95, "usd_rub": 85, "jpy_rub": 0.58,'
        ' "cbrf_date": "01.01.2026"}',
    )
    assert valid_prod.is_production is True

    with pytest.raises(ValidationError, match="CBRF_FALLBACK_RATES"):
        AppSettings(
            _env_file=None,
            ENVIRONMENT="production",
            DEBUG=False,
            SECRET_KEY="x" * 40,
            ALLOWED_HOSTS=["api.yuzu.ru"],
        )


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


@pytest.mark.parametrize(
    "field,value",
    [
        ("CBRF_TIMEOUT_SEC", 0),
        ("CBRF_TIMEOUT_SEC", float("inf")),
        ("CBRF_JPY_SPREAD", -0.01),
        ("CBRF_JPY_SPREAD", float("nan")),
        ("CBRF_JPY_SPREAD", float("inf")),
    ],
)
def test_currency_settings_reject_invalid_numbers(field, value) -> None:
    with pytest.raises(ValidationError):
        AppSettings(_env_file=None, **{field: value})


@pytest.mark.parametrize(
    "overrides",
    [
        {"eur_rub": "NaN"},
        {"usd_rub": "Infinity"},
        {"jpy_rub": 0},
        {"cbrf_date": "31.02.2026"},
        {"cbrf_date": "2026-01-01"},
    ],
)
def test_currency_reserves_are_validated_at_startup(overrides) -> None:
    reserves = {"eur_rub": 95, "usd_rub": 85, "jpy_rub": 0.58, "cbrf_date": "01.01.2026"}
    with pytest.raises(ValidationError, match="CBRF_FALLBACK_RATES"):
        AppSettings(_env_file=None, CBRF_FALLBACK_RATES={**reserves, **overrides})


@pytest.mark.parametrize("reserves", [{}, {"eur_rub": 95}])
def test_incomplete_currency_reserves_are_rejected(reserves) -> None:
    with pytest.raises(ValidationError, match="CBRF_FALLBACK_RATES"):
        AppSettings(_env_file=None, CBRF_FALLBACK_RATES=reserves)
