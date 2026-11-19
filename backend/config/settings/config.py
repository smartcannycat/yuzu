import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from apps.integrations.currency.domain import parse_fallback_config

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_REPO_ROOT = _BACKEND_DIR.parent

_LOT_PARSER_BACKEND_ALIASES: dict[str, str] = {
    "ml": "apps.integrations.ml.parser.MlServiceParser",
}

_TOML_SECTION_PREFIXES: dict[str, str] = {
    "app": "",
    "jwt": "JWT_",
    "media": "MEDIA_",
    "ml_service": "ML_SERVICE_",
    "scraper": "SCRAPER_",
    "farpost": "FARPOST_",
    "aleado": "ALEADO_",
    "currency": "CBRF_",
}


def _flatten_toml_sections(data: dict[str, Any]) -> dict[str, Any]:
    """Flatten `[section]` tables from `config.toml` onto uppercase `AppSettings` keys."""
    flattened: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict) and key in _TOML_SECTION_PREFIXES:
            prefix = _TOML_SECTION_PREFIXES[key]
            for sub_key, sub_value in value.items():
                flattened[f"{prefix}{sub_key}".upper()] = sub_value
        else:
            flattened[key.upper()] = value
    return flattened


class _SectionedTomlSettingsSource(TomlConfigSettingsSource):
    """Load `backend/config.toml` and flatten known sections to `AppSettings` fields."""

    def _read_file(self, file_path: Any) -> dict[str, Any]:
        return _flatten_toml_sections(super()._read_file(file_path))


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", _BACKEND_DIR / ".env", ".env"),
        env_file_encoding="utf-8",
        toml_file=_BACKEND_DIR / "config.toml",
        extra="ignore",
        case_sensitive=False,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Priority: kwargs -> env vars -> .env -> backend/config.toml -> secrets -> defaults."""
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            _SectionedTomlSettingsSource(settings_cls),
            file_secret_settings,
        )

    # Core Application Settings
    ENVIRONMENT: Literal["local", "dev", "test", "production"] = "local"
    DEBUG: bool = True
    SECRET_KEY: str = "django-insecure-default-change-in-production-abcdef123456"
    ALLOWED_HOSTS: list[str] | str = ["*"]
    DJANGO_ADMIN_URL: str = "admin/"
    ADMIN_ALLOWED_IPS: list[str] | str = []

    # CORS Settings
    CORS_ALLOWED_ORIGINS: list[str] | str = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    CORS_ALLOW_ALL_ORIGINS: bool = False
    CSRF_TRUSTED_ORIGINS: list[str] | str = []

    # Database Settings (PostgreSQL only)
    DATABASE_URL: str | None = None
    POSTGRES_DB: str = "yuzu_db"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # JWT Settings
    JWT_ACCESS_TOKEN_LIFETIME_MINUTES: int = 60
    JWT_REFRESH_TOKEN_LIFETIME_DAYS: int = 7
    JWT_SIGNING_KEY: str | None = None

    # Media & Parser
    MEDIA_URL: str = "/media/"
    LOT_PARSER_BACKEND: str = "ml"
    MEDIA_ROOT: str = "media"
    PRIVATE_INTAKE_ROOT: str = "private_intake"

    # External Services (internal ML service URL; public source URLs live in adapters)
    ML_SERVICE_URL: str = "http://127.0.0.1:8001"
    ML_SERVICE_TIMEOUT_SEC: float = 65.0
    ML_SERVICE_API_KEY: str = ""

    # Shared scraper transport & rate-limit settings (used by Drom and Farpost)
    SCRAPER_PROXY_URLS: list[str] | str = []
    SCRAPER_PROXY_BAN_SEC: int = Field(default=120, ge=0)
    SCRAPER_TIMEOUT_SEC: float = Field(default=10.0, gt=0, allow_inf_nan=False)
    SCRAPER_REQUEST_INTERVAL_SEC: float = Field(default=1.2, ge=0, allow_inf_nan=False)
    SCRAPER_REQUEST_JITTER_SEC: float = Field(default=0.4, ge=0, allow_inf_nan=False)

    # Farpost-specific repair workflow settings
    FARPOST_BUDGET_SEC: float = Field(default=30.0, gt=0, allow_inf_nan=False)
    FARPOST_COOLDOWN_SEC: int = Field(default=45, ge=0)
    FARPOST_CACHE_TTL_HOURS: int = Field(default=24, ge=1)
    FARPOST_CAPTCHA_MAX_ATTEMPTS: int = Field(default=2, ge=1, le=5)
    FARPOST_CAPTCHA_SOLVE_BUDGET_SEC: float = Field(default=20.0, gt=0, allow_inf_nan=False)
    FARPOST_CAPTCHA_MAX_WORKERS: int = Field(default=8, ge=1, le=32)
    FARPOST_CAPTCHA_OCR_ENABLED: bool = False
    FARPOST_CAPTCHA_OCR_COMMAND: str = "tesseract"

    # CBRF currency gateway (BE-05)
    CBRF_TIMEOUT_SEC: float = Field(default=5.0, gt=0, allow_inf_nan=False)
    CBRF_JPY_SPREAD: float = Field(default=0.03, ge=0, allow_inf_nan=False)
    CBRF_FALLBACK_RATES: dict[str, str | float] | None = None

    # Aleado cross-audit gateway (BE-08)
    ALEADO_USERNAME: str = ""
    ALEADO_PASSWORD: str = ""
    ALEADO_TIMEOUT_SEC: float = Field(default=20.0, gt=0, allow_inf_nan=False)
    ALEADO_REQUEST_INTERVAL_SEC: float = Field(default=1.0, gt=0, allow_inf_nan=False)
    ALEADO_VERIFY_CANDIDATES: int = Field(default=10, ge=0, le=50)

    # Redis / Celery worker, rate limiting & media retention
    REDIS_URL: str = ""
    CELERY_BROKER_URL: str = ""
    CELERY_TASK_ALWAYS_EAGER: bool = False
    RATE_LIMIT_ENABLED: bool = True
    MEDIA_PURGE_DELETED_AFTER_DAYS: int = Field(default=7, ge=0)
    MEDIA_PURGE_BATCH_ORIGINALS_AFTER_HOURS: int = Field(default=24, ge=0)

    @field_validator("LOT_PARSER_BACKEND")
    @classmethod
    def resolve_lot_parser_backend(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            return ""
        alias = _LOT_PARSER_BACKEND_ALIASES.get(cleaned.lower())
        if alias is not None:
            return alias
        if "." not in cleaned:
            raise ValueError(
                "LOT_PARSER_BACKEND must be 'ml', '' (disabled), or a dotted class path"
            )
        return cleaned

    @field_validator("DJANGO_ADMIN_URL")
    @classmethod
    def normalize_admin_url(cls, value: str) -> str:
        cleaned = (value or "").strip().strip("/")
        return f"{cleaned}/" if cleaned else "admin/"

    @field_validator(
        "ALLOWED_HOSTS",
        "ADMIN_ALLOWED_IPS",
        "CORS_ALLOWED_ORIGINS",
        "CSRF_TRUSTED_ORIGINS",
        "SCRAPER_PROXY_URLS",
    )
    @classmethod
    def parse_comma_separated_list(cls, value: list[str] | str) -> list[str]:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in stripped.split(",") if item.strip()]
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    @field_validator("CBRF_FALLBACK_RATES", mode="before")
    @classmethod
    def parse_fallback_json(cls, value: dict | str | None) -> dict | None:
        if value is None or isinstance(value, dict):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError("CBRF_FALLBACK_RATES must be a JSON object") from exc
            if isinstance(parsed, dict):
                return parsed
        raise ValueError("CBRF_FALLBACK_RATES must be a JSON object")

    @field_validator("CBRF_FALLBACK_RATES")
    @classmethod
    def validate_fallback_rates(cls, value: dict | None) -> dict | None:
        parse_fallback_config(value)
        return value

    @model_validator(mode="after")
    def validate_production_security(self) -> "AppSettings":
        if not self.is_production:
            return self

        if self.DEBUG:
            raise ValueError("DEBUG must be False when ENVIRONMENT=production")
        if self.SECRET_KEY.startswith("django-insecure-") or len(self.SECRET_KEY) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters and not use an insecure default "
                "when ENVIRONMENT=production"
            )
        jwt_key = (self.JWT_SIGNING_KEY or "").strip()
        if len(jwt_key) < 32 or jwt_key == self.SECRET_KEY.strip():
            raise ValueError(
                "JWT_SIGNING_KEY must be at least 32 characters and distinct from SECRET_KEY "
                "when ENVIRONMENT=production"
            )
        ml_api_key = (self.ML_SERVICE_API_KEY or "").strip()
        if not ml_api_key or ml_api_key == "dev-ml-service-key":
            raise ValueError(
                "ML_SERVICE_API_KEY must be set to a non-default secret when ENVIRONMENT=production"
            )
        if not self.ALLOWED_HOSTS or "*" in self.ALLOWED_HOSTS:
            raise ValueError(
                "ALLOWED_HOSTS must explicitly list allowed hostnames (not empty or '*') "
                "when ENVIRONMENT=production"
            )
        if self.CORS_ALLOW_ALL_ORIGINS:
            raise ValueError("CORS_ALLOW_ALL_ORIGINS must be False when ENVIRONMENT=production")
        if not self.CBRF_FALLBACK_RATES:
            raise ValueError(
                "CBRF_FALLBACK_RATES must be set (eur_rub, usd_rub, jpy_rub, cbrf_date) "
                "when ENVIRONMENT=production"
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT == "test"


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
