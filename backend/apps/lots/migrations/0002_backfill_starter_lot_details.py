from django.db import migrations


def backfill_starter_lot_details(apps, schema_editor):
    from apps.lots.models import Lot
    from apps.lots.services import backfill_starter_lots

    historical_lot = apps.get_model("lots", "Lot")
    historical_fields = {field.name for field in historical_lot._meta.concrete_fields}
    backfill_starter_lots(
        defer_fields=tuple(
            field.name for field in Lot._meta.concrete_fields if field.name not in historical_fields
        ),
        customs_model=apps.get_model("lots", "CustomsCalculation"),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("lots", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            backfill_starter_lot_details,
            migrations.RunPython.noop,
        ),
    ]
