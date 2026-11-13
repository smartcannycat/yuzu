from typing import Literal

from django.http import HttpRequest
from ninja import Query, Status, UploadedFile
from ninja_extra import ControllerBase, api_controller, http_delete, http_get, http_patch, http_post
from pydantic import UUID4

from apps.core.enums import LotLifecycleFilter, TrafficLightColor
from apps.core.exceptions import UnauthorizedProblemError
from apps.core.schemas import ProblemDetail
from apps.lots import services
from apps.lots.schemas import (
    BatchCreateResponse,
    BatchProgressResponse,
    LotBulkDeleteRequest,
    LotBulkDeleteResponse,
    LotDetailResponse,
    LotLifecyclePatchRequest,
    LotListResponse,
    LotSummary,
    RecalculateRequest,
    RecalculateResponse,
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

    @http_get(
        "",
        response={
            200: LotListResponse,
            401: ProblemDetail,
            422: ProblemDetail,
        },
    )
    def list_lots(
        self,
        request: HttpRequest,
        query: str | None = None,
        make: str | None = None,
        model: str | None = None,
        verdict: TrafficLightColor | None = None,
        has_anomaly: bool | None = None,
        lifecycle: LotLifecycleFilter = LotLifecycleFilter.ACTIVE,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        sort_by: Literal["created_at", "net_benefit", "turnkey_cost"] = "created_at",
        sort_order: Literal["desc", "asc"] = "desc",
    ) -> LotListResponse:
        user = self._require_user(request)
        return services.get_lots_list(
            user,
            query=query,
            make=make,
            model=model,
            verdict=verdict,
            has_anomaly=has_anomaly,
            lifecycle=lifecycle,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

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
            422: ProblemDetail,
        },
    )
    def get_batch_progress(
        self,
        request: HttpRequest,
        batch_id: UUID4,
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
        batch_id: UUID4,
        files: list[UploadedFile],
    ) -> Status[BatchProgressResponse]:
        user = self._require_user(request)
        return Status(202, services.append_batch_items(user, batch_id, files))

    @http_post(
        "/bulk-delete",
        response={
            200: LotBulkDeleteResponse,
            401: ProblemDetail,
            422: ProblemDetail,
        },
    )
    def bulk_delete_lots(
        self,
        request: HttpRequest,
        payload: LotBulkDeleteRequest,
    ) -> LotBulkDeleteResponse:
        user = self._require_user(request)
        return services.bulk_delete_lots(user, payload.lot_ids)

    @http_get(
        "/{lot_id}",
        response={
            200: LotDetailResponse,
            401: ProblemDetail,
            404: ProblemDetail,
            422: ProblemDetail,
        },
    )
    def get_lot_detail(
        self,
        request: HttpRequest,
        lot_id: UUID4,
    ) -> LotDetailResponse:
        user = self._require_user(request)
        return services.get_lot_detail(user, lot_id)

    @http_post(
        "/{lot_id}/recalculate",
        response={
            200: RecalculateResponse,
            400: ProblemDetail,
            401: ProblemDetail,
            404: ProblemDetail,
            422: ProblemDetail,
        },
    )
    def recalculate_lot(
        self,
        request: HttpRequest,
        lot_id: UUID4,
        payload: RecalculateRequest,
    ) -> RecalculateResponse:
        user = self._require_user(request)
        return services.recalculate_lot(user, lot_id, payload)

    @http_patch(
        "/{lot_id}",
        response={
            200: LotSummary,
            401: ProblemDetail,
            404: ProblemDetail,
            422: ProblemDetail,
        },
    )
    def update_lot_lifecycle(
        self,
        request: HttpRequest,
        lot_id: UUID4,
        payload: LotLifecyclePatchRequest,
    ) -> LotSummary:
        user = self._require_user(request)
        return services.update_lot_lifecycle(
            user,
            lot_id,
            is_archived=payload.is_archived,
        )

    @http_delete(
        "/{lot_id}",
        response={
            204: None,
            401: ProblemDetail,
            404: ProblemDetail,
            422: ProblemDetail,
        },
    )
    def delete_lot(
        self,
        request: HttpRequest,
        lot_id: UUID4,
    ) -> Status:
        user = self._require_user(request)
        services.delete_lot(user, lot_id)
        return Status(204, None)
