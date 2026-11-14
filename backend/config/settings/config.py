import json
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from apps.lots.integrations.currency.domain import parse_fallback_config


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Core Application Settings
    ENVIRONMENT: Literal["local", "dev", "test", "production"] = "local"
    DEBUG: bool = True
    SECRET_KEY: str = "django-insecure-default-change-in-production-abcdef123456"
    ALLOWED_HOSTS: list[str] | str = ["*"]

    # CORS Settings
    CORS_ALLOWED_ORIGINS: list[str] | str = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    CORS_ALLOW_ALL_ORIGINS: bool = False

    # Database Settings (PostgreSQL is the default for dev, test, and prod)
    USE_SQLITE: bool = False
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

    # Media Files
    MEDIA_URL: str = "/media/"
    LOT_PARSER_BACKEND: str = ""
    MEDIA_ROOT: str = "media"

    # External Services
    ML_SERVICE_URL: str = "http://127.0.0.1:8001"
    ML_SERVICE_TIMEOUT_SEC: float = 30.0
    ML_SERVICE_API_KEY: str = ""
    CBRF_API_URL: str = "https://www.cbr-xml-daily.ru/daily_json.js"
    HTTP_CLIENT_TIMEOUT_SEC: float = 10.0
    FARPOST_TIMEOUT_SEC: float = Field(default=8.0, gt=0, allow_inf_nan=False)
    FARPOST_BUDGET_SEC: float = Field(default=30.0, gt=0, allow_inf_nan=False)
    FARPOST_REQUEST_INTERVAL_SEC: float = Field(default=1.5, ge=0, allow_inf_nan=False)
    FARPOST_COOLDOWN_SEC: int = Field(default=180, ge=0)
    FARPOST_CACHE_TTL_HOURS: int = Field(default=6, ge=1)

    # CBRF currency gateway (BE-05)
    CBRF_TIMEOUT_SEC: float = Field(default=5.0, gt=0, allow_inf_nan=False)
    CBRF_JPY_SPREAD: float = Field(default=0.03, ge=0, allow_inf_nan=False)
    CBRF_FALLBACK_RATES: dict[str, str | float] | None = None

    # Aleado cross-audit gateway (BE-08)
    ALEADO_BASE_URL: str = "https://auc.aleado.com"
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

    @field_validator("ALLOWED_HOSTS", "CORS_ALLOWED_ORIGINS")
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

        if self.SECRET_KEY.startswith("django-insecure-") or len(self.SECRET_KEY) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters and not use an insecure default "
                "when ENVIRONMENT=production"
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
