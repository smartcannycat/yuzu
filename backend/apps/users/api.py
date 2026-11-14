from django.http import HttpRequest
from ninja import Status
from ninja_extra import ControllerBase, api_controller, http_get, http_post

from apps.core.exceptions import UnauthorizedProblemError
from apps.core.redis_utils import enforce_rate_limit, get_client_ip
from apps.core.schemas import ProblemDetail
from apps.users.authentication import AppJWTAuth
from apps.users.models import User
from apps.users.schemas import (
    AuthTokensResponse,
    TokenRefreshRequest,
    UserLoginRequest,
    UserProfileResponse,
    UserRegisterRequest,
)
from apps.users.services import (
    authenticate_user,
    build_user_profile,
    refresh_user_tokens,
    register_user,
)


@api_controller("/auth", tags=["Auth"])
class AuthController(ControllerBase):
    @http_post(
        "/register",
        response={
            201: AuthTokensResponse,
            400: ProblemDetail,
            409: ProblemDetail,
            422: ProblemDetail,
            429: ProblemDetail,
        },
    )
    def register(
        self, request: HttpRequest, payload: UserRegisterRequest
    ) -> Status[AuthTokensResponse]:
        enforce_rate_limit(
            "auth:register",
            get_client_ip(request),
            limit=10,
            window_sec=60,
            detail="Слишком много попыток регистрации. Попробуйте позже.",
        )
        return Status(201, register_user(payload))

    @http_post(
        "/login",
        response={
            200: AuthTokensResponse,
            400: ProblemDetail,
            401: ProblemDetail,
            422: ProblemDetail,
            429: ProblemDetail,
        },
    )
    def login(self, request: HttpRequest, payload: UserLoginRequest) -> AuthTokensResponse:
        client_ip = get_client_ip(request)
        normalized_email = payload.email.strip().lower()
        enforce_rate_limit(
            "auth:login:ip",
            client_ip,
            limit=40,
            window_sec=60,
            detail="Слишком много попыток входа. Попробуйте через минуту.",
        )
        enforce_rate_limit(
            "auth:login:account",
            f"{client_ip}:{normalized_email}",
            limit=15,
            window_sec=60,
            detail="Слишком много попыток входа для этого аккаунта. Попробуйте через минуту.",
        )
        return authenticate_user(payload, request=request)

    @http_post(
        "/refresh",
        response={
            200: AuthTokensResponse,
            400: ProblemDetail,
            401: ProblemDetail,
            422: ProblemDetail,
            429: ProblemDetail,
        },
    )
    def refresh(self, request: HttpRequest, payload: TokenRefreshRequest) -> AuthTokensResponse:
        enforce_rate_limit(
            "auth:refresh",
            get_client_ip(request),
            limit=30,
            window_sec=60,
            detail="Слишком много запросов обновления токена. Попробуйте позже.",
        )
        return refresh_user_tokens(payload)

    @http_get(
        "/me",
        auth=AppJWTAuth(),
        response={200: UserProfileResponse, 401: ProblemDetail},
    )
    def me(self, request: HttpRequest) -> UserProfileResponse:
        if not isinstance(request.auth, User):
            raise UnauthorizedProblemError(
                "Отсутствует или недействителен токен авторизации",
                title="Требуется авторизация",
            )
        return build_user_profile(request.auth)
