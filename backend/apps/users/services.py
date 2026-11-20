from dataclasses import dataclass
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.exceptions import DisallowedHost
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from ninja_jwt.exceptions import TokenError
from ninja_jwt.settings import api_settings as jwt_settings
from ninja_jwt.tokens import RefreshToken

from apps.core.exceptions import (
    ConflictProblemError,
    ForbiddenProblemError,
    UnauthorizedProblemError,
)
from apps.lots.services import seed_starter_lots
from apps.users.models import User, UserManager
from apps.users.schemas import (
    AuthTokensResponse,
    UserLoginRequest,
    UserProfileResponse,
    UserRegisterRequest,
)


@dataclass(frozen=True)
class IssuedAuthTokens:
    response_body: AuthTokensResponse
    refresh_token: str


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
) -> IssuedAuthTokens:
    token = refresh_token or RefreshToken.for_user(user)
    expires_in_sec = int(jwt_settings.ACCESS_TOKEN_LIFETIME.total_seconds())
    return IssuedAuthTokens(
        response_body=AuthTokensResponse(
            access_token=str(token.access_token),
            token_type="bearer",
            expires_in_sec=expires_in_sec,
            user=build_user_profile(user),
        ),
        refresh_token=str(token),
    )


def set_refresh_cookie(response: HttpResponse, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.JWT_REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=int(jwt_settings.REFRESH_TOKEN_LIFETIME.total_seconds()),
        httponly=True,
        secure=not settings.DEBUG,
        samesite=settings.JWT_REFRESH_COOKIE_SAMESITE,
        path=settings.JWT_REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: HttpResponse) -> None:
    response.set_cookie(
        key=settings.JWT_REFRESH_COOKIE_NAME,
        value="",
        max_age=0,
        expires="Thu, 01 Jan 1970 00:00:00 GMT",
        httponly=True,
        secure=not settings.DEBUG,
        samesite=settings.JWT_REFRESH_COOKIE_SAMESITE,
        path=settings.JWT_REFRESH_COOKIE_PATH,
    )


def _parse_origin_pair(raw_url: str) -> tuple[str, str] | None:
    parsed = urlparse((raw_url or "").strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    if scheme not in {"http", "https"} or not netloc:
        return None
    return scheme, netloc


def _allowed_request_origins(request: HttpRequest) -> set[tuple[str, str]]:
    allowed: set[tuple[str, str]] = set()
    for raw in (
        *(getattr(settings, "CORS_ALLOWED_ORIGINS", []) or []),
        *(getattr(settings, "CSRF_TRUSTED_ORIGINS", []) or []),
    ):
        pair = _parse_origin_pair(str(raw))
        if pair is not None:
            allowed.add(pair)
    try:
        host = request.get_host().lower()
    except DisallowedHost:
        host = ""
    if host:
        allowed.add((request.scheme.lower(), host))
    return allowed


def enforce_cookie_csrf_protection(request: HttpRequest) -> None:
    """Require same-origin Origin/Referer or explicit SPA header on cookie-auth endpoints."""
    origin = (request.headers.get("Origin") or "").strip()
    if origin:
        pair = _parse_origin_pair(origin)
        if pair is not None and pair in _allowed_request_origins(request):
            return
        raise ForbiddenProblemError(
            "Запрос отклонен: недопустимый заголовок Origin",
            title="Проверка безопасности не пройдена",
        )

    referer = (request.headers.get("Referer") or "").strip()
    if referer:
        pair = _parse_origin_pair(referer)
        if pair is not None and pair in _allowed_request_origins(request):
            return
        raise ForbiddenProblemError(
            "Запрос отклонен: недопустимый заголовок Referer",
            title="Проверка безопасности не пройдена",
        )

    if (request.headers.get("X-Requested-With") or "").strip() == "YuzuSPA":
        return

    raise ForbiddenProblemError(
        "Требуется доверенный Origin/Referer или заголовок X-Requested-With: YuzuSPA",
        title="Проверка безопасности не пройдена",
    )


@transaction.atomic
def register_user(payload: UserRegisterRequest) -> IssuedAuthTokens:
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

    seed_starter_lots(user)
    return issue_auth_tokens(user)


def authenticate_user(
    payload: UserLoginRequest,
    *,
    request: HttpRequest | None = None,
) -> IssuedAuthTokens:
    normalized_email = UserManager.normalize_email(payload.email)
    user = authenticate(request=request, username=normalized_email, password=payload.password)
    if user is None or not isinstance(user, User) or not user.is_active:
        raise UnauthorizedProblemError(
            "Неверный email или пароль",
            title="Неверные учетные данные",
        )

    return issue_auth_tokens(user)


@transaction.atomic
def refresh_user_tokens(raw_refresh_token: str) -> IssuedAuthTokens:
    try:
        token = RefreshToken(raw_refresh_token)
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
        user = User.objects.select_for_update().filter(id=user_id, is_active=True).first()
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
                _, created = token.blacklist()
            except (AttributeError, TokenError) as exc:
                raise UnauthorizedProblemError(
                    "Refresh-токен уже отозван или недействителен",
                    title="Сессия истекла",
                ) from exc
            if not created:
                raise UnauthorizedProblemError(
                    "Refresh-токен уже отозван или недействителен",
                    title="Сессия истекла",
                )
        return issue_auth_tokens(user)

    return issue_auth_tokens(user, refresh_token=token)


def logout_user_session(raw_refresh_token: str | None) -> None:
    if not raw_refresh_token:
        return
    try:
        token = RefreshToken(raw_refresh_token)
        token.blacklist()
    except (AttributeError, TokenError):
        return
