from functools import lru_cache
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=(_SERVICE_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

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
    gemini_rpm_limit: int = Field(default=5, ge=1, le=600)
    gemini_request_timeout_ms: int = Field(default=25000, ge=5000, le=300000)
    gemini_sdk_max_attempts: int = Field(default=1, ge=1, le=5)
    gemini_model_cooldown_seconds: float = Field(default=120.0, ge=0.0, le=600.0)
    gemini_key_cooldown_seconds: float = Field(default=30.0, ge=0.0, le=600.0)
    gemini_thinking_level: str = Field(default="LOW")

    crop_format: str = Field(default="JPEG")
    crop_quality: int = Field(default=88, ge=50, le=100)
    crop_min_px: int = Field(default=1000, ge=400, le=2400)
    crop_max_px: int = Field(default=1400, ge=600, le=2400)

    max_image_size_mb: int = Field(default=15, ge=1, le=50)
    http_timeout_seconds: float = Field(default=20.0, gt=0)

    cache_dir: Path = Field(default=_SERVICE_ROOT / ".cache" / "sheets")
    reference_year: int = Field(default=2026, ge=2020, le=2035)

    @field_validator("cache_dir", mode="after")
    @classmethod
    def _resolve_relative_cache_dir(cls, value: Path) -> Path:
        if not value.is_absolute():
            return (_SERVICE_ROOT / value).resolve()
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
    def gemini_api_keys(self) -> list[str]:
        """Returns clean list of API keys from pool or single key fallback."""
        keys = [
            k.strip()
            for k in self.gemini_api_keys_raw.split(",")
            if k.strip() and not k.strip().startswith("your_api_key")
        ]
        single = self.gemini_api_key_single.strip()
        if not keys and single and not single.startswith("your_api_key"):
            keys.append(single)
        return keys

    @property
    def max_image_bytes(self) -> int:
        return self.max_image_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance loaded from environment."""
    return Settings()
