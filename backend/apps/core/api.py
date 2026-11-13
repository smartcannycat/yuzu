from django.db import DatabaseError, connection
from ninja_extra import ControllerBase, api_controller, http_get

from apps.core.exceptions import ERROR_TYPE_BASE, ApiProblemError
from apps.core.schemas import HealthSchema, ProblemDetail


@api_controller("/health", tags=["Health"])
class HealthController(ControllerBase):
    @http_get("", response={200: HealthSchema, 503: ProblemDetail})
    def health_check(self) -> HealthSchema:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError as exc:
            raise ApiProblemError(
                "База данных недоступна",
                title="Сервис временно недоступен",
                status_code=503,
                error_type=f"{ERROR_TYPE_BASE}/service-unavailable",
            ) from exc

        return HealthSchema(status="ok")
