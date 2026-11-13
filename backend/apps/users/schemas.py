from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import EmailStr, Field, StringConstraints

from apps.core.schemas import StrictBaseModel

RegisterPasswordStr = Annotated[
    str,
    StringConstraints(strip_whitespace=False, min_length=8, max_length=128),
]
LoginPasswordStr = Annotated[
    str,
    StringConstraints(strip_whitespace=False, min_length=1),
]


class UserRegisterRequest(StrictBaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: RegisterPasswordStr = Field(..., description="User password")
    name: str | None = Field(None, max_length=100, description="Optional display name")


class UserLoginRequest(StrictBaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: LoginPasswordStr = Field(..., description="User password")


class TokenRefreshRequest(StrictBaseModel):
    refresh_token: str = Field(..., min_length=1, description="Valid refresh JWT token")


class UserProfileResponse(StrictBaseModel):
    user_id: UUID = Field(..., description="User UUID")
    email: str = Field(..., description="User email address")
    name: str | None = Field(None, description="User display name")
    created_at: datetime = Field(..., description="Registration timestamp in UTC")


class AuthTokensResponse(StrictBaseModel):
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: Literal["bearer"] = Field("bearer", description="Authorization scheme")
    expires_in_sec: int = Field(..., description="Access token lifetime in seconds")
    user: UserProfileResponse = Field(..., description="Authenticated user profile")
