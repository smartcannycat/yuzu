from django.apps import AppConfig


class LotsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.lots"

    def ready(self) -> None:
        from apps.lots.services import recover_batches_on_startup

        recover_batches_on_startup()
