import pytest
from pydantic import ValidationError

from config.settings.base import _build_database_config
from config.settings.config import AppSettings


def test_app_settings_parses_json_and_csv_lists() -> None:
    settings_json = AppSettings(
        _env_file=None,
        ALLOWED_HOSTS='["api.yuzu.ru", "localhost"]',
        ADMIN_ALLOWED_IPS="10.0.0.1, 192.168.1.0/24",
        CORS_ALLOWED_ORIGINS="https://yuzu.ru, https://app.yuzu.ru",
        DJANGO_ADMIN_URL="/ops-console",
    )
    assert settings_json.ALLOWED_HOSTS == ["api.yuzu.ru", "localhost"]
    assert settings_json.ADMIN_ALLOWED_IPS == ["10.0.0.1", "192.168.1.0/24"]
    assert settings_json.CORS_ALLOWED_ORIGINS == ["https://yuzu.ru", "https://app.yuzu.ru"]
    assert settings_json.DJANGO_ADMIN_URL == "ops-console/"


def test_production_settings_reject_insecure_defaults() -> None:
    base_prod_kwargs = {
        "_env_file": None,
        "ENVIRONMENT": "production",
        "DEBUG": False,
        "SECRET_KEY": "x" * 40,
        "JWT_SIGNING_KEY": "y" * 40,
        "ML_SERVICE_API_KEY": "prod-ml-secret-key",
        "ALLOWED_HOSTS": ["api.yuzu.ru"],
        "CBRF_FALLBACK_RATES": (
            '{"eur_rub": 95, "usd_rub": 85, "jpy_rub": 0.58, "cbrf_date": "01.01.2026"}'
        ),
    }

    with pytest.raises(ValidationError, match="DEBUG"):
        AppSettings(**{**base_prod_kwargs, "DEBUG": True})

    with pytest.raises(ValidationError, match="SECRET_KEY"):
        AppSettings(**{**base_prod_kwargs, "SECRET_KEY": "django-insecure-short"})

    with pytest.raises(ValidationError, match="JWT_SIGNING_KEY"):
        AppSettings(**{**base_prod_kwargs, "JWT_SIGNING_KEY": None})

    with pytest.raises(ValidationError, match="JWT_SIGNING_KEY"):
        AppSettings(**{**base_prod_kwargs, "JWT_SIGNING_KEY": "short-key"})

    with pytest.raises(ValidationError, match="JWT_SIGNING_KEY"):
        AppSettings(**{**base_prod_kwargs, "JWT_SIGNING_KEY": "x" * 40})

    with pytest.raises(ValidationError, match="ML_SERVICE_API_KEY"):
        AppSettings(**{**base_prod_kwargs, "ML_SERVICE_API_KEY": ""})

    with pytest.raises(ValidationError, match="ML_SERVICE_API_KEY"):
        AppSettings(**{**base_prod_kwargs, "ML_SERVICE_API_KEY": "dev-ml-service-key"})

    with pytest.raises(ValidationError, match="ALLOWED_HOSTS"):
        AppSettings(**{**base_prod_kwargs, "ALLOWED_HOSTS": ["*"]})

    with pytest.raises(ValidationError, match="CBRF_FALLBACK_RATES"):
        AppSettings(**{**base_prod_kwargs, "CBRF_FALLBACK_RATES": None})

    valid_prod = AppSettings(**base_prod_kwargs)
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


def test_sqlite_is_removed_from_settings_and_database_config() -> None:
    assert not hasattr(AppSettings, "USE_SQLITE")
    with pytest.raises(ValueError, match="Unsupported DATABASE_URL scheme: sqlite"):
        _build_database_config(AppSettings(_env_file=None, DATABASE_URL="sqlite:///db.sqlite3"))


def test_backend_config_toml_loaded_with_env_override(monkeypatch) -> None:
    from_toml = AppSettings(_env_file=None)
    assert from_toml.FARPOST_BUDGET_SEC == 30.0
    assert from_toml.CBRF_JPY_SPREAD == 0.03
    assert from_toml.ALEADO_VERIFY_CANDIDATES == 10
    assert from_toml.ML_SERVICE_TIMEOUT_SEC == 65.0
    assert from_toml.DJANGO_ADMIN_URL == "admin/"
    assert from_toml.PRIVATE_INTAKE_ROOT == "private_intake"

    monkeypatch.setenv("FARPOST_BUDGET_SEC", "45.5")
    overridden = AppSettings(_env_file=None)
    assert overridden.FARPOST_BUDGET_SEC == 45.5


def test_lot_parser_backend_aliases_and_removed_source_urls() -> None:
    default_settings = AppSettings(_env_file=None)
    assert default_settings.LOT_PARSER_BACKEND == "apps.integrations.ml.parser.MlServiceParser"
    assert not hasattr(default_settings, "ALEADO_BASE_URL")
    assert not hasattr(default_settings, "CBRF_API_URL")

    disabled = AppSettings(_env_file=None, LOT_PARSER_BACKEND="  ")
    assert disabled.LOT_PARSER_BACKEND == ""

    custom = AppSettings(_env_file=None, LOT_PARSER_BACKEND="custom.module.Parser")
    assert custom.LOT_PARSER_BACKEND == "custom.module.Parser"

    with pytest.raises(ValidationError, match="LOT_PARSER_BACKEND"):
        AppSettings(_env_file=None, LOT_PARSER_BACKEND="unknown_backend")
