from datetime import UTC, datetime
from typing import Any

from django.db.models import Manager
from ninja import Schema
from pydantic import ConfigDict, Field, field_validator


class StrictBaseModel(Schema):
    """Base schema matching strict API contract validation rules."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True,
    )

    @field_validator("*", mode="before")
    @classmethod
    def load_related_records(cls, value: Any) -> Any:
        return list(value.all()) if isinstance(value, Manager) else value


class InvalidParamDetail(StrictBaseModel):
    name: str = Field(..., description="Field or header name with validation error")
    reason: str = Field(..., description="Human-readable validation failure reason")


class ProblemDetail(StrictBaseModel):
    """RFC 7807 Problem Details response schema."""

    type: str = Field("about:blank", description="Error type URI")
    title: str = Field(..., description="Short summary of the error")
    status: int = Field(..., description="HTTP status code")
    detail: str = Field(..., description="Detailed human-readable explanation")
    instance: str | None = Field(None, description="Endpoint URI where error occurred")
    invalid_params: list[InvalidParamDetail] = Field(
        default_factory=list,
        description="List of invalid request parameters",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Error timestamp in UTC",
    )


class HealthSchema(StrictBaseModel):
    status: str = "ok"
