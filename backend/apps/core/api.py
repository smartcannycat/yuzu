from ninja_extra import ControllerBase, api_controller, http_get

from apps.core.schemas import HealthSchema


@api_controller("/health", tags=["Health"])
class HealthController(ControllerBase):
    @http_get("", response={200: HealthSchema})
    def health_check(self) -> HealthSchema:
        return HealthSchema(status="ok")
