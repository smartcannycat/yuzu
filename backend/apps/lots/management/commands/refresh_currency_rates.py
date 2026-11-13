"""Warm the CBRF currency rates cache manually (BE-05)."""

from django.core.management.base import BaseCommand

from apps.lots.integrations.currency.service import build_currency_service


class Command(BaseCommand):
    help = "Fetch CBRF currency rates and warm the read-through cache"

    def handle(self, *_args, **_options) -> None:
        service = build_currency_service()
        result = service.refresh()
        self.stdout.write(
            self.style.SUCCESS(
                f"origin={result.origin.value} "
                f"cbrf_date={result.cbrf_date} "
                f"EUR={result.eur_rub} USD={result.usd_rub} JPY={result.jpy_rub} "
                f"JPY_bank={result.commercial_jpy_rub} "
                f"is_fallback={result.is_fallback} reason={result.fallback_reason}"
            )
        )
