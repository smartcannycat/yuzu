from django.db import migrations


def backfill_starter_lot_details(apps, schema_editor):
    from apps.lots.services import backfill_starter_lots

    backfill_starter_lots()


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
