from django.http import HttpRequest
from ninja import Status
from ninja_extra import ControllerBase, api_controller, http_get, http_post

from apps.core.exceptions import UnauthorizedProblemError
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
        },
    )
    def register(self, payload: UserRegisterRequest) -> Status[AuthTokensResponse]:
        return Status(201, register_user(payload))

    @http_post(
        "/login",
        response={
            200: AuthTokensResponse,
            400: ProblemDetail,
            401: ProblemDetail,
            422: ProblemDetail,
        },
    )
    def login(self, request: HttpRequest, payload: UserLoginRequest) -> AuthTokensResponse:
        return authenticate_user(payload, request=request)

    @http_post(
        "/refresh",
        response={
            200: AuthTokensResponse,
            400: ProblemDetail,
            401: ProblemDetail,
            422: ProblemDetail,
        },
    )
    def refresh(self, payload: TokenRefreshRequest) -> AuthTokensResponse:
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
