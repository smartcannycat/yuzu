from uuid import UUID

from django.http import HttpRequest
from ninja import Status, UploadedFile
from ninja_extra import ControllerBase, api_controller, http_get, http_post

from apps.core.exceptions import UnauthorizedProblemError
from apps.core.schemas import ProblemDetail
from apps.lots import services
from apps.lots.schemas import (
    BatchCreateResponse,
    BatchProgressResponse,
)
from apps.users.authentication import AppJWTAuth
from apps.users.models import User


@api_controller("/lots", tags=["Lots"], auth=AppJWTAuth())
class LotController(ControllerBase):
    def _require_user(self, request: HttpRequest) -> User:
        if not isinstance(request.auth, User):
            raise UnauthorizedProblemError(
                "Отсутствует или недействителен токен авторизации",
                title="Требуется авторизация",
            )
        return request.auth

    @http_post(
        "/batches",
        response={
            202: BatchCreateResponse,
            400: ProblemDetail,
            401: ProblemDetail,
            422: ProblemDetail,
        },
    )
    def create_batch(
        self,
        request: HttpRequest,
        files: list[UploadedFile],
    ) -> Status[BatchCreateResponse]:
        user = self._require_user(request)
        return Status(202, services.create_batch(user, files))

    @http_get(
        "/batches/{batch_id}",
        response={
            200: BatchProgressResponse,
            401: ProblemDetail,
            404: ProblemDetail,
        },
    )
    def get_batch_progress(
        self,
        request: HttpRequest,
        batch_id: UUID,
    ) -> BatchProgressResponse:
        user = self._require_user(request)
        return services.get_batch_progress(user, batch_id)

    @http_post(
        "/batches/{batch_id}/items",
        response={
            202: BatchProgressResponse,
            400: ProblemDetail,
            401: ProblemDetail,
            404: ProblemDetail,
            409: ProblemDetail,
            422: ProblemDetail,
        },
    )
    def append_batch_items(
        self,
        request: HttpRequest,
        batch_id: UUID,
        files: list[UploadedFile],
    ) -> Status[BatchProgressResponse]:
        user = self._require_user(request)
        return Status(202, services.append_batch_items(user, batch_id, files))
