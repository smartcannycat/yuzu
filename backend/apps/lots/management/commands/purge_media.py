"""Management command to purge stale media files for soft-deleted lots and uploads."""

from django.core.management.base import BaseCommand

from apps.lots.media_purge import purge_stale_media


class Command(BaseCommand):
    help = "Delete stale media files from deleted lots and old completed batches."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--deleted-days",
            type=int,
            default=None,
            help="Purge media for lots soft-deleted at least N days ago.",
        )
        parser.add_argument(
            "--originals-hours",
            type=int,
            default=None,
            help="Purge raw BatchItem uploads for terminal batches older than N hours.",
        )

    def handle(self, *_args, **options) -> None:
        result = purge_stale_media(
            deleted_after_days=options["deleted_days"],
            originals_after_hours=options["originals_hours"],
        )
        self.stdout.write(
            f"Purged deleted_lots_files={result['deleted_lots_files']} "
            f"batch_originals_files={result['batch_originals_files']}"
        )
