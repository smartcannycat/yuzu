from ninja_extra import NinjaExtraAPI

from apps.core.api import HealthController
from apps.core.exception_handlers import register_exception_handlers
from apps.users.api import AuthController

api = NinjaExtraAPI(
    title="Yuzu API",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

register_exception_handlers(api)

api.register_controllers(
    HealthController,
    AuthController,
)
