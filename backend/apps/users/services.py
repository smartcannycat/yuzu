from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.http import HttpRequest
from ninja_jwt.exceptions import TokenError
from ninja_jwt.settings import api_settings as jwt_settings
from ninja_jwt.tokens import RefreshToken

from apps.core.exceptions import ConflictProblemError, UnauthorizedProblemError
from apps.users.models import User, UserManager
from apps.users.schemas import (
    AuthTokensResponse,
    TokenRefreshRequest,
    UserLoginRequest,
    UserProfileResponse,
    UserRegisterRequest,
)


def build_user_profile(user: User) -> UserProfileResponse:
    return UserProfileResponse(
        user_id=user.id,
        email=user.email,
        name=user.name,
        created_at=user.created_at,
    )


def issue_auth_tokens(
    user: User,
    *,
    refresh_token: RefreshToken | None = None,
) -> AuthTokensResponse:
    token = refresh_token or RefreshToken.for_user(user)
    expires_in_sec = int(jwt_settings.ACCESS_TOKEN_LIFETIME.total_seconds())
    return AuthTokensResponse(
        access_token=str(token.access_token),
        refresh_token=str(token),
        token_type="bearer",
        expires_in_sec=expires_in_sec,
        user=build_user_profile(user),
    )


def register_user(payload: UserRegisterRequest) -> AuthTokensResponse:
    normalized_email = UserManager.normalize_email(payload.email)
    normalized_name = payload.name or None

    if User.objects.filter(email=normalized_email).exists():
        raise ConflictProblemError(
            "Пользователь с таким email уже зарегистрирован",
            title="Email уже занят",
        )

    try:
        user = User.objects.create_user(
            email=normalized_email,
            password=payload.password,
            name=normalized_name,
        )
    except IntegrityError as exc:
        raise ConflictProblemError(
            "Пользователь с таким email уже зарегистрирован",
            title="Email уже занят",
        ) from exc

    # Starter benchmark lots seeding (BE-02/BE-04) will be hooked here once Lot models exist.
    return issue_auth_tokens(user)


def authenticate_user(
    payload: UserLoginRequest,
    *,
    request: HttpRequest | None = None,
) -> AuthTokensResponse:
    normalized_email = UserManager.normalize_email(payload.email)
    user = authenticate(request=request, username=normalized_email, password=payload.password)
    if user is None or not isinstance(user, User) or not user.is_active:
        raise UnauthorizedProblemError(
            "Неверный email или пароль",
            title="Неверные учетные данные",
        )

    return issue_auth_tokens(user)


@transaction.atomic
def refresh_user_tokens(payload: TokenRefreshRequest) -> AuthTokensResponse:
    try:
        token = RefreshToken(payload.refresh_token)
    except TokenError as exc:
        raise UnauthorizedProblemError(
            "Refresh-токен недействителен или истек",
            title="Сессия истекла",
        ) from exc

    user_id = token.get(jwt_settings.USER_ID_CLAIM)
    if not user_id:
        raise UnauthorizedProblemError(
            "Токен не содержит идентификатор пользователя",
            title="Сессия истекла",
        )

    try:
        user = User.objects.filter(id=user_id, is_active=True).first()
    except (ValueError, DjangoValidationError) as exc:
        raise UnauthorizedProblemError(
            "Токен содержит некорректный идентификатор пользователя",
            title="Сессия истекла",
        ) from exc

    if user is None:
        raise UnauthorizedProblemError(
            "Пользователь не найден или деактивирован",
            title="Сессия истекла",
        )

    if jwt_settings.ROTATE_REFRESH_TOKENS:
        if jwt_settings.BLACKLIST_AFTER_ROTATION:
            try:
                token.blacklist()
            except (AttributeError, TokenError) as exc:
                raise UnauthorizedProblemError(
                    "Refresh-токен уже отозван или недействителен",
                    title="Сессия истекла",
                ) from exc
        return issue_auth_tokens(user)

    return issue_auth_tokens(user, refresh_token=token)
