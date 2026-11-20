"""Backfill legacy Lot.bid_slider_min_jpy values from 300000 to 100000."""

from django.db import migrations


def backfill_bid_slider_min_jpy(apps, schema_editor):
    Lot = apps.get_model("lots", "Lot")
    Lot.objects.filter(bid_slider_min_jpy=300_000).update(bid_slider_min_jpy=100_000)


class Migration(migrations.Migration):

    dependencies = [
        ("lots", "0009_alter_batchitem_original_file_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_bid_slider_min_jpy, migrations.RunPython.noop),
    ]
