from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_ROOT = Path(__file__).resolve().parent
_RUNTIME_ROOT = Path.cwd() if "site-packages" in _SERVICE_ROOT.parts else _SERVICE_ROOT


def _parse_key_list(
    keys_raw: str,
    single_key: str,
    placeholder_prefixes: tuple[str, ...] = ("your_api_key", "your_ml_service_api_key", "change_me"),
) -> list[str]:
    """Parse comma-separated API keys with single-key fallback, filtering template placeholders."""
    keys = [
        item.strip()
        for item in keys_raw.split(",")
        if item.strip() and not item.strip().startswith(placeholder_prefixes)
    ]
    single = single_key.strip()
    if not keys and single and not single.startswith(placeholder_prefixes):
        keys.append(single)
    return keys


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=(_SERVICE_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    ml_service_api_keys_raw: str = Field(default="", validation_alias="ML_SERVICE_API_KEYS")
    ml_service_api_key_single: str = Field(default="", validation_alias="ML_SERVICE_API_KEY")

    gemini_api_keys_raw: str = Field(default="", validation_alias="GEMINI_API_KEYS")
    gemini_api_key_single: str = Field(default="", validation_alias="GEMINI_API_KEY")

    gemini_decision_model: str = Field(default="gemini-decision-1")
    gemini_flash_model: str = Field(default="gemini-3.6-flash")
    gemini_fallback_models_raw: str = Field(
        default="gemini-3-flash-preview,gemini-3.7-flash,gemini-3.8-flash,gemini-3.5-flash,gemini-3.5-flash-lite",
        validation_alias="GEMINI_FALLBACK_MODELS",
    )
    enable_gatekeeper: bool = Field(default=True)
    gemini_gatekeeper_fail_open: bool = Field(default=True)
    gemini_gatekeeper_sheet_threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    gemini_gatekeeper_readable_threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    gemini_rpm_limit: int = Field(default=5, ge=1, le=600)
    gemini_request_timeout_ms: int = Field(default=25000, ge=5000, le=300000)
    gemini_sdk_max_attempts: int = Field(default=1, ge=1, le=5)
    gemini_model_cooldown_seconds: float = Field(default=120.0, ge=0.0, le=600.0)
    gemini_client_error_cooldown_seconds: float = Field(default=300.0, ge=0.0, le=3600.0)
    gemini_key_cooldown_seconds: float = Field(default=30.0, ge=0.0, le=600.0)
    gemini_max_key_tries: int = Field(default=3, ge=1, le=20)
    gemini_thinking_level: str = Field(default="LOW")
    gemini_request_deadline_seconds: float = Field(default=45.0, ge=5.0, le=300.0)
    gemini_hedge_delay_seconds: float = Field(default=8.0, ge=0.5, le=120.0)
    gemini_fast_header_timeout_seconds: float = Field(default=1.2, ge=0.1, le=10.0)
    default_auction_strictness: float = Field(default=0.65, ge=0.0, le=1.0)
    batch_poll_interval_ms: int = Field(default=1500, ge=100, le=60000)
    batch_max_items: int = Field(default=10, ge=1, le=50)
    batch_max_concurrency: int = Field(default=3, ge=1, le=20)
    batch_max_stored_batches: int = Field(default=200, ge=1, le=10000)
    batch_ttl_seconds: float = Field(default=1800.0, ge=10.0, le=86400.0)
    rate_limit_requests_per_minute: int = Field(default=120, ge=0, le=10000)

    crop_format: str = Field(default="JPEG")
    crop_quality: int = Field(default=88, ge=50, le=100)
    crop_min_px: int = Field(default=1000, ge=400, le=2400)
    crop_max_px: int = Field(default=1400, ge=600, le=2400)

    max_image_size_mb: int = Field(default=15, ge=1, le=50)
    http_timeout_seconds: float = Field(default=20.0, gt=0)

    cache_dir: Path = Field(default=_RUNTIME_ROOT / ".cache" / "sheets")
    reference_year: int = Field(default=2026, ge=2020, le=2035)
    reference_month: int = Field(default=11, ge=1, le=12)

    @field_validator("cache_dir", mode="after")
    @classmethod
    def _resolve_relative_cache_dir(cls, value: Path) -> Path:
        if not value.is_absolute():
            return (_RUNTIME_ROOT / value).resolve()
        return value

    @property
    def gemini_fallback_models(self) -> list[str]:
        """Return deduplicated fallback model names excluding the primary flash model."""
        seen: set[str] = {self.gemini_flash_model.strip()}
        models: list[str] = []
        for raw in self.gemini_fallback_models_raw.split(","):
            name = raw.strip()
            if name and name not in seen:
                seen.add(name)
                models.append(name)
        return models

    @property
    def service_api_keys(self) -> list[str]:
        """Return clean list of accepted X-API-Key secrets from pool or single-key fallback."""
        return _parse_key_list(self.ml_service_api_keys_raw, self.ml_service_api_key_single)

    @property
    def gemini_api_keys(self) -> list[str]:
        """Returns clean list of API keys from pool or single key fallback."""
        return _parse_key_list(self.gemini_api_keys_raw, self.gemini_api_key_single)

    @property
    def max_image_bytes(self) -> int:
        return self.max_image_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance loaded from environment."""
    return Settings()
