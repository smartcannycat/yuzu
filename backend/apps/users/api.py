import hashlib

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from ninja import Status
from ninja_extra import ControllerBase, api_controller, http_get, http_post

from apps.core.exceptions import UnauthorizedProblemError
from apps.core.redis_utils import enforce_rate_limit, get_client_ip
from apps.core.schemas import ProblemDetail
from apps.users.authentication import AppJWTAuth
from apps.users.models import User, UserManager
from apps.users.schemas import (
    AuthTokensResponse,
    UserLoginRequest,
    UserProfileResponse,
    UserRegisterRequest,
)
from apps.users.services import (
    authenticate_user,
    build_user_profile,
    clear_refresh_cookie,
    enforce_cookie_csrf_protection,
    logout_user_session,
    refresh_user_tokens,
    register_user,
    set_refresh_cookie,
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
        self,
        request: HttpRequest,
        response: HttpResponse,
        payload: UserRegisterRequest,
    ) -> Status[AuthTokensResponse]:
        enforce_rate_limit(
            "auth:register",
            get_client_ip(request),
            limit=10,
            window_sec=60,
            detail="Слишком много попыток регистрации. Попробуйте позже.",
        )
        issued = register_user(payload)
        set_refresh_cookie(response, issued.refresh_token)
        return Status(201, issued.response_body)

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
    def login(
        self,
        request: HttpRequest,
        response: HttpResponse,
        payload: UserLoginRequest,
    ) -> AuthTokensResponse:
        client_ip = get_client_ip(request)
        normalized_email = UserManager.normalize_email(payload.email)
        email_hash = hashlib.sha256(normalized_email.encode("utf-8")).hexdigest()
        enforce_rate_limit(
            "auth:login:ip",
            client_ip,
            limit=40,
            window_sec=60,
            detail="Слишком много попыток входа. Попробуйте через минуту.",
        )
        enforce_rate_limit(
            "auth:login:email",
            email_hash,
            limit=10,
            window_sec=60,
            detail="Слишком много попыток входа для этого аккаунта. Попробуйте через минуту.",
        )
        issued = authenticate_user(payload, request=request)
        set_refresh_cookie(response, issued.refresh_token)
        return issued.response_body

    @http_post(
        "/refresh",
        response={
            200: AuthTokensResponse,
            401: ProblemDetail,
            403: ProblemDetail,
            429: ProblemDetail,
        },
    )
    def refresh(
        self,
        request: HttpRequest,
        response: HttpResponse,
    ) -> AuthTokensResponse:
        enforce_cookie_csrf_protection(request)
        enforce_rate_limit(
            "auth:refresh",
            get_client_ip(request),
            limit=30,
            window_sec=60,
            detail="Слишком много запросов обновления токена. Попробуйте позже.",
        )
        raw_refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
        if not raw_refresh:
            raise UnauthorizedProblemError(
                "Refresh-токен отсутствует",
                title="Сессия истекла",
            )
        issued = refresh_user_tokens(raw_refresh)
        set_refresh_cookie(response, issued.refresh_token)
        return issued.response_body

    @http_post(
        "/logout",
        response={
            204: None,
            403: ProblemDetail,
        },
    )
    def logout(
        self,
        request: HttpRequest,
        response: HttpResponse,
    ) -> Status:
        enforce_cookie_csrf_protection(request)
        logout_user_session(request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME))
        clear_refresh_cookie(response)
        return Status(204, None)

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
