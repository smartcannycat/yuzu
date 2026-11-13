from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    MEDIA_ROOT: str = "media"

    # External Services
    ML_SERVICE_URL: str = "http://127.0.0.1:8001"
    ML_SERVICE_TIMEOUT_SEC: float = 30.0
    CBRF_API_URL: str = "https://www.cbr-xml-daily.ru/daily_json.js"
    HTTP_CLIENT_TIMEOUT_SEC: float = 10.0

    @field_validator("ALLOWED_HOSTS", "CORS_ALLOWED_ORIGINS")
    @classmethod
    def parse_comma_separated_list(cls, value: list[str] | str) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value]
        return []

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT == "test"


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
