from django.core.management.base import BaseCommand

from apps.lots.integrations.drom.schema_sync import DEFAULT_SCHEMA_PATH, sync_drom_schema


class Command(BaseCommand):
    help = "Scrape Drom.ru brand/model slugs and filter schema into drom_schema.json"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--workers",
            type=int,
            default=10,
            help="Parallel worker count for scraping Drom brand pages.",
        )

    def handle(self, *_args, **options) -> None:
        workers = max(1, int(options["workers"]))
        schema = sync_drom_schema(DEFAULT_SCHEMA_PATH, max_workers=workers)
        brands = schema.get("brands", {})
        sales_count = sum(len(b.get("sales_models", {})) for b in brands.values())
        catalog_count = sum(len(b.get("catalog_models", {})) for b in brands.values())
        self.stdout.write(
            self.style.SUCCESS(
                f"Synced {len(brands)} brands, {sales_count} sales models, "
                f"{catalog_count} catalog models -> {DEFAULT_SCHEMA_PATH}"
            )
        )
