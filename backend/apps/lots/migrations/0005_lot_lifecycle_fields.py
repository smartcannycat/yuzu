from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lots", "0004_lot_auction_bid_jpy_lot_customs_rates_input_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="lot",
            name="archived_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="lot",
            name="archived_reason",
            field=models.CharField(
                blank=True,
                choices=[("expired", "Expired"), ("manual", "Manual")],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="lot",
            name="auction_date",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name="lot",
            name="auto_archive_disabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="lot",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="lot",
            name="expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="lot",
            name="is_archived",
            field=models.BooleanField(default=False),
        ),
        migrations.AddIndex(
            model_name="lot",
            index=models.Index(
                fields=["user", "deleted_at", "is_archived"],
                name="lots_user_del_arch_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="lot",
            index=models.Index(
                fields=["user", "deleted_at", "expires_at"],
                name="lots_user_del_exp_idx",
            ),
        ),
    ]
